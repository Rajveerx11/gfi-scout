"""`find_issues` MCP tool — Phase 1 implementation."""

from __future__ import annotations

from urllib.parse import urlparse

from gfi_scout.models.issue import GitHubIssueRaw, IssueResult
from gfi_scout.services.github_api import GitHubAPIError, GitHubClient
from gfi_scout.utils.logger import get_logger
from gfi_scout.utils.validators import clamp_max_results, validate_language

DEFAULT_LABELS = ("good first issue",)
BODY_PREVIEW_CHARS = 280

log = get_logger(__name__)


def build_search_query(
    *,
    language: str,
    labels: list[str],
    min_stars: int,
    max_stars: int,
    topic: str | None,
) -> str:
    """Compose a GitHub Search API qualifier string."""
    parts: list[str] = []
    for label in labels:
        parts.append(f'label:"{label}"')
    parts.append(f"language:{language}")
    parts.append(f"stars:{min_stars}..{max_stars}")
    parts.append("state:open")
    parts.append("is:issue")
    parts.append("no:assignee")
    if topic:
        parts.append(f"topic:{topic}")
    return " ".join(parts)


def _repo_full_name_from_repository_url(repository_url: str) -> str:
    """Derive `owner/repo` from a GitHub API `repository_url`.

    The Search API returns e.g. `https://api.github.com/repos/owner/name`.
    """
    path = urlparse(repository_url).path.removeprefix("/repos/")
    return path.strip("/")


def _to_result(item: GitHubIssueRaw) -> IssueResult:
    body = item.body or ""
    preview = body[:BODY_PREVIEW_CHARS]
    if len(body) > BODY_PREVIEW_CHARS:
        preview = preview.rstrip() + "…"
    return IssueResult(
        title=item.title,
        url=item.html_url,
        body_preview=preview,
        repo_full_name=_repo_full_name_from_repository_url(str(item.repository_url)),
        repo_stars=None,
        repo_language=None,
        labels=[label.name for label in item.labels],
        is_assigned=item.assignee is not None or len(item.assignees) > 0,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def find_issues(
    client: GitHubClient,
    *,
    language: str,
    min_stars: int = 50,
    max_stars: int = 50000,
    labels: list[str] | None = None,
    max_results: int = 10,
    sort_by: str = "beginner_score",  # noqa: ARG001 — wired but unused in Phase 1
    topic: str | None = None,
) -> list[IssueResult]:
    """Search GitHub for beginner-friendly issues.

    Phase 1: language + label + star-range filter via the Search API. The
    `sort_by` parameter is accepted for forward compatibility but ranking
    lands in Phase 2 alongside the scoring engine.
    """
    cleaned_language = validate_language(language)
    capped = clamp_max_results(max_results)
    label_list = list(labels) if labels else list(DEFAULT_LABELS)

    query = build_search_query(
        language=cleaned_language,
        labels=label_list,
        min_stars=min_stars,
        max_stars=max_stars,
        topic=topic,
    )
    log.info("find_issues query=%r max_results=%d", query, capped)

    try:
        response = await client.search_issues(query, per_page=capped, page=1)
    except GitHubAPIError as exc:
        log.error("find_issues failed: %s", exc)
        raise

    return [_to_result(item) for item in response.items[:capped]]
