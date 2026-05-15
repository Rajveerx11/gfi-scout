"""Input validation helpers."""

from __future__ import annotations

import re
from urllib.parse import urlparse

MAX_RESULTS_HARD_CAP = 25
LANGUAGE_MAX_LENGTH = 64
LABEL_MAX_LENGTH = 64
TOPIC_MAX_LENGTH = 50
REPO_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ISSUE_URL_RE = re.compile(
    r"^https?://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/issues/(\d+)(?:[/?#].*)?$"
)
TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")


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


def validate_label(label: str) -> str:
    """Validate a GitHub issue label for safe inclusion in a search query.

    Labels are interpolated into `label:"..."` qualifiers, so they must not
    contain characters that could break out of the quoted value (`"`, newlines,
    control chars) or introduce new search qualifiers.
    """
    if not isinstance(label, str):
        raise ValidationError("label must be a string")
    cleaned = label.strip()
    if not cleaned:
        raise ValidationError("label must not be empty")
    if len(cleaned) > LABEL_MAX_LENGTH:
        raise ValidationError(f"label too long (>{LABEL_MAX_LENGTH} chars)")
    for ch in cleaned:
        if ch == '"' or ch == "\\" or ord(ch) < 0x20:
            raise ValidationError("label contains disallowed character")
    return cleaned


def validate_topic(topic: str) -> str:
    """Validate a GitHub topic slug (lowercase alphanumerics + hyphens)."""
    if not isinstance(topic, str):
        raise ValidationError("topic must be a string")
    cleaned = topic.strip().lower()
    if not cleaned:
        raise ValidationError("topic must not be empty")
    if len(cleaned) > TOPIC_MAX_LENGTH:
        raise ValidationError(f"topic too long (>{TOPIC_MAX_LENGTH} chars)")
    if not TOPIC_RE.match(cleaned):
        raise ValidationError(
            "topic must be lowercase alphanumerics or hyphens, start with alphanumeric"
        )
    return cleaned


def parse_issue_url(url: str) -> tuple[str, int]:
    """Parse a GitHub issue URL into (`owner/repo`, issue_number)."""
    if not isinstance(url, str):
        raise ValidationError("issue_url must be a string")
    match = ISSUE_URL_RE.match(url.strip())
    if not match:
        raise ValidationError("issue_url must look like https://github.com/owner/repo/issues/N")
    return match.group(1), int(match.group(2))
