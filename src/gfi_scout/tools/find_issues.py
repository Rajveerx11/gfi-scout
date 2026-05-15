"""`find_issues` MCP tool — Phase 2 implementation with scoring + parallelism."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from gfi_scout.models.issue import GitHubIssueRaw, IssueResult
from gfi_scout.models.repo import RepoHealth
from gfi_scout.services.github_api import GitHubAPIError, GitHubClient
from gfi_scout.services.issue_scorer import (
    compute_beginner_score,
    freshness_label,
)
from gfi_scout.services.repo_analyzer import analyse_repo
from gfi_scout.services.scoring_config import ScoringConfig
from gfi_scout.utils.logger import get_logger
from gfi_scout.utils.validators import clamp_max_results, validate_language

DEFAULT_LABELS = ("good first issue",)
BODY_PREVIEW_CHARS = 280
ALLOWED_SORTS = ("beginner_score", "freshness", "repo_health")
DEFAULT_HEALTH_CONCURRENCY = 5

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
    path = urlparse(repository_url).path.removeprefix("/repos/")
    return path.strip("/")


def _body_preview(raw_body: str | None) -> str:
    body = raw_body or ""
    preview = body[:BODY_PREVIEW_CHARS]
    if len(body) > BODY_PREVIEW_CHARS:
        preview = preview.rstrip() + "…"
    return preview


def _sort_results(
    results: list[IssueResult],
    sort_by: str,
) -> list[IssueResult]:
    if sort_by == "freshness":
        return sorted(results, key=lambda r: r.updated_at, reverse=True)
    if sort_by == "repo_health":
        grade_rank = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1, None: 0}
        return sorted(
            results,
            key=lambda r: grade_rank.get(r.repo_health_grade, 0),
            reverse=True,
        )
    # default: beginner_score
    return sorted(
        results,
        key=lambda r: r.beginner_score or 0,
        reverse=True,
    )


async def _gather_repo_health(
    client: GitHubClient,
    repos: list[str],
    *,
    cfg: ScoringConfig,
    concurrency: int,
) -> dict[str, RepoHealth | None]:
    sem = asyncio.Semaphore(concurrency)

    async def one(repo: str) -> tuple[str, RepoHealth | None]:
        async with sem:
            try:
                health = await analyse_repo(client, repo, cfg=cfg)
                return repo, health
            except GitHubAPIError as exc:
                log.warning("repo health failed for %s: %s", repo, exc)
                return repo, None

    pairs = await asyncio.gather(*(one(r) for r in repos))
    return dict(pairs)


def _to_result(
    item: GitHubIssueRaw,
    *,
    health: RepoHealth | None,
    cfg: ScoringConfig,
    enable_scoring: bool,
) -> IssueResult:
    beginner_score_value: int | None = None
    freshness = None
    grade = None
    if enable_scoring:
        score_payload = compute_beginner_score(item, health, cfg=cfg)
        beginner_score_value = score_payload.score
        freshness = freshness_label(item, cfg)
        grade = health.health_grade if health else None
    repo_full_name = _repo_full_name_from_repository_url(str(item.repository_url))
    return IssueResult(
        title=item.title,
        url=item.html_url,
        body_preview=_body_preview(item.body),
        repo_full_name=repo_full_name,
        repo_stars=None,
        repo_language=None,
        labels=[label.name for label in item.labels],
        is_assigned=item.assignee is not None or len(item.assignees) > 0,
        created_at=item.created_at,
        updated_at=item.updated_at,
        beginner_score=beginner_score_value,
        freshness=freshness,
        repo_health_grade=grade,
    )


async def find_issues(
    client: GitHubClient,
    *,
    language: str,
    cfg: ScoringConfig | None = None,
    min_stars: int = 50,
    max_stars: int = 50000,
    labels: list[str] | None = None,
    max_results: int = 10,
    sort_by: str = "beginner_score",
    topic: str | None = None,
    enable_scoring: bool = True,
    health_concurrency: int = DEFAULT_HEALTH_CONCURRENCY,
) -> list[IssueResult]:
    """Search GitHub for beginner-friendly issues, scored and ranked.

    Phase 2: pulls repo-health metrics in parallel for every returned issue's
    repo and computes a `beginner_score` per issue. Sort by `beginner_score`
    (default), `freshness`, or `repo_health`.
    """
    cleaned_language = validate_language(language)
    capped = clamp_max_results(max_results)
    label_list = list(labels) if labels else list(DEFAULT_LABELS)
    if sort_by not in ALLOWED_SORTS:
        sort_by = "beginner_score"

    query = build_search_query(
        language=cleaned_language,
        labels=label_list,
        min_stars=min_stars,
        max_stars=max_stars,
        topic=topic,
    )
    log.info("find_issues query=%r max_results=%d sort_by=%s", query, capped, sort_by)

    try:
        response = await client.search_issues(query, per_page=capped, page=1)
    except GitHubAPIError as exc:
        log.error("find_issues failed: %s", exc)
        raise

    items = response.items[:capped]
    if not items:
        return []

    # Compute scoring inputs in parallel.
    healths: dict[str, RepoHealth | None] = {}
    effective_cfg = cfg
    if enable_scoring:
        from gfi_scout.services.scoring_config import get_scoring_config

        effective_cfg = cfg or get_scoring_config()
        unique_repos = sorted(
            {_repo_full_name_from_repository_url(str(item.repository_url)) for item in items}
        )
        healths = await _gather_repo_health(
            client,
            unique_repos,
            cfg=effective_cfg,
            concurrency=health_concurrency,
        )

    results: list[IssueResult] = []
    for item in items:
        repo = _repo_full_name_from_repository_url(str(item.repository_url))
        results.append(
            _to_result(
                item,
                health=healths.get(repo) if enable_scoring else None,
                cfg=effective_cfg if enable_scoring else None,  # type: ignore[arg-type]
                enable_scoring=enable_scoring,
            )
        )
    return _sort_results(results, sort_by)
