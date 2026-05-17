"""`find_issues` MCP tool — repo-first search with scoring + parallelism.

GitHub's `/search/issues` endpoint does not honour the `stars:` qualifier
(stars belong to repositories, not issues). The previous query shape
silently returned zero results against the live API. This implementation
searches repositories by `stars:` first, then fans out per-repo issue
listings for the desired labels — a clean two-stage flow that aligns with
how GitHub's data model is actually shaped.
"""

from __future__ import annotations

import asyncio

from gfi_scout.models.issue import GitHubIssueRaw, IssueResult
from gfi_scout.models.repo import RepoHealth, RepoSummary
from gfi_scout.services.github_api import GitHubAPIError, GitHubClient
from gfi_scout.services.issue_scorer import (
    compute_beginner_score,
    freshness_label,
)
from gfi_scout.services.repo_analyzer import analyse_repo
from gfi_scout.services.scoring_config import ScoringConfig
from gfi_scout.utils.logger import get_logger
from gfi_scout.utils.validators import (
    clamp_max_results,
    validate_label,
    validate_language,
    validate_topic,
)

DEFAULT_LABELS = ("good first issue",)
BODY_PREVIEW_CHARS = 280
ALLOWED_SORTS = ("beginner_score", "freshness", "repo_health")
DEFAULT_HEALTH_CONCURRENCY = 5
DEFAULT_ISSUE_CONCURRENCY = 5
REPO_OVERFETCH_MULTIPLIER = 3
REPO_SEARCH_MAX = 30
PER_REPO_ISSUE_FETCH = 10

log = get_logger(__name__)


def build_repo_search_query(
    *,
    language: str,
    min_stars: int,
    max_stars: int,
    topic: str | None,
) -> str:
    """Compose a GitHub `/search/repositories` qualifier string.

    Inputs are assumed to be pre-validated (`validate_language`, `validate_topic`).
    Star bounds are coerced to a sane non-negative range before interpolation.
    """
    parts: list[str] = [f"language:{language}"]
    lo = max(0, int(min_stars))
    hi = max(lo, int(max_stars))
    parts.append(f"stars:{lo}..{hi}")
    if topic:
        parts.append(f"topic:{topic}")
    return " ".join(parts)


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


async def _gather_repo_issues(
    client: GitHubClient,
    repos: list[RepoSummary],
    *,
    labels: list[str],
    per_repo_limit: int,
    concurrency: int,
) -> dict[str, list[GitHubIssueRaw]]:
    sem = asyncio.Semaphore(concurrency)

    async def one(repo: RepoSummary) -> tuple[str, list[GitHubIssueRaw]]:
        async with sem:
            try:
                issues = await client.list_repo_issues(
                    repo.full_name,
                    labels=labels,
                    state="open",
                    per_page=per_repo_limit,
                )
                return repo.full_name, issues
            except GitHubAPIError as exc:
                log.warning("repo issue list failed for %s: %s", repo.full_name, exc)
                return repo.full_name, []

    pairs = await asyncio.gather(*(one(r) for r in repos))
    return dict(pairs)


def _to_result(
    item: GitHubIssueRaw,
    *,
    repo_summary: RepoSummary,
    health: RepoHealth | None,
    cfg: ScoringConfig | None,
    enable_scoring: bool,
) -> IssueResult:
    beginner_score_value: int | None = None
    freshness = None
    grade = None
    if enable_scoring and cfg is not None:
        score_payload = compute_beginner_score(item, health, cfg=cfg)
        beginner_score_value = score_payload.score
        freshness = freshness_label(item, cfg)
        grade = health.health_grade if health else None
    return IssueResult(
        title=item.title,
        url=item.html_url,
        body_preview=_body_preview(item.body),
        repo_full_name=repo_summary.full_name,
        repo_stars=repo_summary.stars,
        repo_language=repo_summary.language,
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
    unassigned_only: bool = True,
    enable_scoring: bool = True,
    health_concurrency: int = DEFAULT_HEALTH_CONCURRENCY,
    issue_concurrency: int = DEFAULT_ISSUE_CONCURRENCY,
) -> list[IssueResult]:
    """Search GitHub for beginner-friendly issues, scored and ranked.

    Two-stage flow: search repositories matching `language`, `stars`, and
    optional `topic`; then fan out per-repo issue listings for the requested
    labels. Repo health is computed in parallel for every matched repo when
    scoring is enabled. Sort by `beginner_score` (default), `freshness`, or
    `repo_health`.

    When `unassigned_only=True` (default), issues already assigned to someone
    are filtered out client-side. Set to False to widen the result set.
    """
    cleaned_language = validate_language(language)
    capped = clamp_max_results(max_results)
    raw_labels = list(labels) if labels else list(DEFAULT_LABELS)
    label_list = [validate_label(label) for label in raw_labels]
    cleaned_topic = validate_topic(topic) if topic else None
    if sort_by not in ALLOWED_SORTS:
        sort_by = "beginner_score"

    repo_query = build_repo_search_query(
        language=cleaned_language,
        min_stars=min_stars,
        max_stars=max_stars,
        topic=cleaned_topic,
    )
    repo_search_limit = min(
        REPO_SEARCH_MAX,
        max(capped, capped * REPO_OVERFETCH_MULTIPLIER),
    )
    log.info(
        "find_issues repo_query=%r repo_limit=%d labels=%s max_results=%d sort_by=%s",
        repo_query,
        repo_search_limit,
        label_list,
        capped,
        sort_by,
    )

    try:
        repos = await client.search_repositories(
            repo_query,
            sort="stars",
            order="desc",
            per_page=repo_search_limit,
            page=1,
        )
    except GitHubAPIError as exc:
        log.error("find_issues repo search failed: %s", exc)
        raise

    if not repos:
        return []

    try:
        issues_by_repo = await _gather_repo_issues(
            client,
            repos,
            labels=label_list,
            per_repo_limit=PER_REPO_ISSUE_FETCH,
            concurrency=issue_concurrency,
        )
    except GitHubAPIError as exc:
        log.error("find_issues issue fan-out failed: %s", exc)
        raise

    repo_summaries: dict[str, RepoSummary] = {r.full_name: r for r in repos}
    flat: list[tuple[RepoSummary, GitHubIssueRaw]] = []
    for repo in repos:
        for issue in issues_by_repo.get(repo.full_name, []):
            if unassigned_only and (
                issue.assignee is not None or len(issue.assignees) > 0
            ):
                continue
            flat.append((repo, issue))

    if not flat:
        return []

    flat = flat[: capped * REPO_OVERFETCH_MULTIPLIER]

    healths: dict[str, RepoHealth | None] = {}
    effective_cfg: ScoringConfig | None = cfg
    if enable_scoring:
        from gfi_scout.services.scoring_config import get_scoring_config

        effective_cfg = cfg or get_scoring_config()
        unique_repos = sorted({repo.full_name for repo, _ in flat})
        healths = await _gather_repo_health(
            client,
            unique_repos,
            cfg=effective_cfg,
            concurrency=health_concurrency,
        )

    results: list[IssueResult] = []
    for repo_summary, issue in flat:
        results.append(
            _to_result(
                issue,
                repo_summary=repo_summaries[repo_summary.full_name],
                health=healths.get(repo_summary.full_name) if enable_scoring else None,
                cfg=effective_cfg,
                enable_scoring=enable_scoring,
            )
        )

    sorted_results = _sort_results(results, sort_by)
    return sorted_results[:capped]
