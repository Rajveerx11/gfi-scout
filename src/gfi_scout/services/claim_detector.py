"""Detect contributor claims and maintainer confirmation in issue comments."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from importlib import resources
from pathlib import Path

from pydantic import ValidationError

from gfi_scout.models.claim import ClaimDetection, ClaimPhraseConfig


def _default_path() -> Path:
    """Resolve bundled claim phrases from the installed package."""
    return Path(str(resources.files("gfi_scout.data").joinpath("claim_phrases.json")))


DEFAULT_PATH = _default_path()


class ClaimConfigError(RuntimeError):
    """Raised when claim phrase configuration is missing or malformed."""


def load_claim_phrase_config(path: Path | None = None) -> ClaimPhraseConfig:
    """Load and validate claim detection configuration."""
    config_path = path or DEFAULT_PATH
    if not config_path.exists():
        raise ClaimConfigError(f"claim phrase config not found: {config_path}")
    try:
        with config_path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        return ClaimPhraseConfig.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ClaimConfigError(f"invalid claim phrase config: {config_path}") from exc


@lru_cache(maxsize=1)
def get_claim_phrase_config() -> ClaimPhraseConfig:
    """Return cached bundled claim detection configuration."""
    return load_claim_phrase_config()


def _normalise(value: str) -> str:
    value = value.casefold().replace("’", "'")
    return re.sub(r"[^\w']+", " ", value).strip()


def _contains_phrase(body: str, phrases: Sequence[str]) -> bool:
    normalised_body = f" {_normalise(body)} "
    return any(f" {_normalise(phrase)} " in normalised_body for phrase in phrases)


def detect_claim(
    comments: Sequence[Mapping[str, object]],
    *,
    config: ClaimPhraseConfig,
) -> ClaimDetection:
    """Detect claim and explicit maintainer-confirmation phrases."""
    claim_detected = False
    maintainer_confirmed = False

    for comment in comments:
        body = comment.get("body")
        association = comment.get("author_association")
        if not isinstance(body, str) or not isinstance(association, str):
            continue
        if association in config.maintainer_associations:
            maintainer_confirmed = maintainer_confirmed or _contains_phrase(
                body,
                config.maintainer_confirmation_phrases,
            )
        else:
            claim_detected = claim_detected or _contains_phrase(
                body,
                config.claim_phrases,
            )

    return ClaimDetection(
        claim_detected=claim_detected,
        maintainer_confirmed=maintainer_confirmed,
    )
