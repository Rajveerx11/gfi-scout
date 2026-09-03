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
QUOTED_TEXT_RE = re.compile(r'```.*?```|`[^`]*`|"[^"]*"|“[^”]*”', re.DOTALL)
SENTENCE_RE = re.compile(r"([^.!?！？]+)([.!?！？]+|$)")


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


def _confirmation_stances(body: str, config: ClaimPhraseConfig) -> list[tuple[bool, set[str]]]:
    unquoted_lines = [line for line in body.splitlines() if not line.lstrip().startswith(">")]
    unquoted_body = QUOTED_TEXT_RE.sub(" ", "\n".join(unquoted_lines))
    stances: list[tuple[bool, set[str]]] = []
    for sentence_match in SENTENCE_RE.finditer(unquoted_body):
        sentence, punctuation = sentence_match.groups()
        normalised_sentence = _normalise(MENTION_RE.sub(" ", sentence))
        if "?" in punctuation or "？" in punctuation:
            continue
        mentioned_logins = _mentioned_logins(sentence)
        if _contains_phrase(normalised_sentence, config.retraction_phrases):
            stances.append((False, mentioned_logins))
            continue
        candidates = (
            " ".join(part for part in (_normalise(prefix), _normalise(phrase)) if part)
            for phrase in config.maintainer_confirmation_phrases
            for prefix in config.confirmation_prefixes
        )
        if any(normalised_sentence == candidate for candidate in candidates):
            stances.append((True, mentioned_logins))
    return stances


def _claimant_login(comment: Mapping[str, object]) -> str | None:
    user = comment.get("user")
    if not isinstance(user, Mapping):
        return None
    login = user.get("login")
    return login.casefold() if isinstance(login, str) and login else None


def _mentioned_logins(body: str) -> set[str]:
    return {match.casefold() for match in MENTION_RE.findall(body)}


def detect_claim(
    comments: Sequence[Mapping[str, object]],
    *,
    config: ClaimPhraseConfig,
) -> ClaimDetection:
    """Detect claim and explicit maintainer-confirmation phrases."""
    claim_detected = False
    anonymous_claim_detected = False
    anonymous_claim_confirmed = False
    claimant_confirmations: dict[str, bool] = {}
    latest_claimant_login: str | None = None

    for comment in comments:
        body = comment.get("body")
        association = comment.get("author_association")
        if not isinstance(body, str) or not isinstance(association, str):
            continue
        if association in config.maintainer_associations:
            if not claim_detected:
                continue
            for stance, mentioned_logins in _confirmation_stances(body, config):
                if mentioned_logins:
                    matching_logins = mentioned_logins & claimant_confirmations.keys()
                    for login in matching_logins:
                        claimant_confirmations[login] = stance
                elif latest_claimant_login is None:
                    if anonymous_claim_detected:
                        anonymous_claim_confirmed = stance
                else:
                    claimant_confirmations[latest_claimant_login] = stance
            continue

        if _contains_phrase(body, config.claim_phrases):
            claim_detected = True
            claimant_login = _claimant_login(comment)
            if claimant_login is None:
                anonymous_claim_detected = True
            else:
                claimant_confirmations.setdefault(claimant_login, False)
            latest_claimant_login = claimant_login

    return ClaimDetection(
        claim_detected=claim_detected,
        maintainer_confirmed=(anonymous_claim_confirmed or any(claimant_confirmations.values())),
    )
