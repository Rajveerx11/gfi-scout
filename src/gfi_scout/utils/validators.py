"""Input validation helpers."""

from __future__ import annotations

import re
from urllib.parse import urlparse

MAX_RESULTS_HARD_CAP = 25
LANGUAGE_MAX_LENGTH = 64
REPO_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ISSUE_URL_RE = re.compile(
    r"^https?://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/issues/(\d+)(?:[/?#].*)?$"
)


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
        raise ValidationError("language may only contain alphanumerics and '+', '-', '#', '.'")
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


def validate_repo_full_name(repo: str) -> str:
    """Validate an `owner/repo` string. Accepts a full GitHub URL too."""
    if not isinstance(repo, str):
        raise ValidationError("repo must be a string")
    raw = repo.strip()
    if not raw:
        raise ValidationError("repo must not be empty")
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            raise ValidationError("only github.com URLs are supported")
        path = parsed.path.strip("/")
        parts = path.split("/")
        if len(parts) < 2:
            raise ValidationError("URL must include owner/repo")
        raw = f"{parts[0]}/{parts[1]}"
    if not REPO_NAME_RE.match(raw):
        raise ValidationError(f"repo must be 'owner/name' with safe characters, got {repo!r}")
    return raw


def parse_issue_url(url: str) -> tuple[str, int]:
    """Parse a GitHub issue URL into (`owner/repo`, issue_number)."""
    if not isinstance(url, str):
        raise ValidationError("issue_url must be a string")
    match = ISSUE_URL_RE.match(url.strip())
    if not match:
        raise ValidationError("issue_url must look like https://github.com/owner/repo/issues/N")
    return match.group(1), int(match.group(2))
