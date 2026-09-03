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

MENTION_RE = re.compile(r"(?<![\w-])@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))\b")


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


def _claimant_login(comment: Mapping[str, object]) -> str | None:
    user = comment.get("user")
    if not isinstance(user, Mapping):
        return None
    login = user.get("login")
    return login.casefold() if isinstance(login, str) and login else None


def _confirmation_matches_claimant(body: str, claimant_logins: set[str]) -> bool:
    mentioned_logins = {match.casefold() for match in MENTION_RE.findall(body)}
    return not mentioned_logins or not claimant_logins or bool(mentioned_logins & claimant_logins)


def detect_claim(
    comments: Sequence[Mapping[str, object]],
    *,
    config: ClaimPhraseConfig,
) -> ClaimDetection:
    """Detect claim and explicit maintainer-confirmation phrases."""
    claim_detected = False
    maintainer_confirmed = False
    claimant_logins: set[str] = set()

    for comment in comments:
        body = comment.get("body")
        association = comment.get("author_association")
        if not isinstance(body, str) or not isinstance(association, str):
            continue
        if association in config.maintainer_associations:
            if (
                claim_detected
                and _contains_phrase(body, config.maintainer_confirmation_phrases)
                and _confirmation_matches_claimant(body, claimant_logins)
            ):
                maintainer_confirmed = True
            continue

        if _contains_phrase(body, config.claim_phrases):
            claim_detected = True
            claimant_login = _claimant_login(comment)
            if claimant_login is not None:
                claimant_logins.add(claimant_login)

    return ClaimDetection(
        claim_detected=claim_detected,
        maintainer_confirmed=maintainer_confirmed,
    )
