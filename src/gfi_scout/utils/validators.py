"""Input validation helpers."""

from __future__ import annotations

MAX_RESULTS_HARD_CAP = 25
LANGUAGE_MAX_LENGTH = 64


class ValidationError(ValueError):
    """Raised when caller-supplied input is invalid."""


def validate_language(language: str) -> str:
    """Normalise and validate a programming-language name for GitHub search."""
    if not isinstance(language, str):
        raise ValidationError("language must be a string")
    cleaned = language.strip().lower()
    if not cleaned:
        raise ValidationError("language must not be empty")
    if len(cleaned) > LANGUAGE_MAX_LENGTH:
        raise ValidationError(f"language too long (>{LANGUAGE_MAX_LENGTH} chars)")
    if not all(c.isalnum() or c in "+-#." for c in cleaned):
        raise ValidationError(
            "language may only contain alphanumerics and '+', '-', '#', '.'"
        )
    return cleaned


def clamp_max_results(value: int, hard_cap: int = MAX_RESULTS_HARD_CAP) -> int:
    """Clamp a max_results value into the inclusive range [1, hard_cap]."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError("max_results must be an int")
    if value < 1:
        return 1
    if value > hard_cap:
        return hard_cap
    return value
