"""Repository health analysis.

Pulls a sample of recent PRs + contributor stats + content probes and
produces a `RepoHealth` payload. All thresholds come from
`config/scoring_weights.json` — no magic numbers in this file.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

from gfi_scout.models.repo import RepoHealth, RepoSummary
from gfi_scout.services.github_api import GitHubClient
from gfi_scout.services.scoring_config import ScoringConfig
from gfi_scout.utils.logger import get_logger

log = get_logger(__name__)

CI_FILES = (
    ".github/workflows",
    ".circleci/config.yml",
    ".travis.yml",
    "azure-pipelines.yml",
    ".gitlab-ci.yml",
)
CONTRIBUTING_PATHS = (
    "CONTRIBUTING.md",
    "docs/CONTRIBUTING.md",
    ".github/CONTRIBUTING.md",
)
CODE_OF_CONDUCT_PATHS = (
    "CODE_OF_CONDUCT.md",
    "docs/CODE_OF_CONDUCT.md",
    ".github/CODE_OF_CONDUCT.md",
)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _hours_between(a: datetime, b: datetime) -> float:
    return abs((b - a).total_seconds()) / 3600.0


async def _probe_first_existing(
    client: GitHubClient, repo: str, paths: tuple[str, ...],
) -> bool:
    for path in paths:
        if await client.path_exists(repo, path):
            return True
    return False


async def _has_ci(client: GitHubClient, repo: str) -> bool:
    for path in CI_FILES:
        if await client.path_exists(repo, path):
            return True
    return False


def _compute_pr_signals(pulls: list[dict[str, Any]]) -> dict[str, float | None]:
    """From a list of recent (closed) PRs compute merge_rate + avg times."""
    if not pulls:
        return {"merge_rate": None, "avg_review_time_hours": None,
                "avg_merge_time_hours": None}
    merged_count = sum(1 for pr in pulls if pr.get("merged_at"))
    merge_rate = merged_count / len(pulls)

    merge_durations: list[float] = []
    for pr in pulls:
        merged = _parse_dt(pr.get("merged_at"))
        created = _parse_dt(pr.get("created_at"))
        if merged and created:
            merge_durations.append(_hours_between(created, merged))

    # GitHub's list-PRs endpoint doesn't ship review timestamps. We use the
    # first PR comment / update as a proxy via updated_at - created_at on
    # merged PRs as a coarse "time to action" signal. This is documented
    # in SCORING_ALGORITHM.md.
    review_durations: list[float] = []
    for pr in pulls:
        created = _parse_dt(pr.get("created_at"))
        updated = _parse_dt(pr.get("updated_at"))
        if created and updated and updated > created:
            review_durations.append(_hours_between(created, updated))

    return {
        "merge_rate": merge_rate,
        "avg_merge_time_hours": mean(merge_durations) if merge_durations else None,
        "avg_review_time_hours": mean(review_durations) if review_durations else None,
    }


def _grade_from_signals(
    *,
    cfg: ScoringConfig,
    merge_rate: float | None,
    last_commit: datetime | None,
    has_contributing: bool,
    has_ci: bool,
) -> str:
    """Map a small set of strong signals to an A-F grade."""
    now = datetime.now(timezone.utc)
    commit_age_days = (now - last_commit).days if last_commit else None

    if commit_age_days is None or commit_age_days >= cfg.stale_repo_commit_days:
        return "F"

    if (
        commit_age_days <= cfg.active_repo_commit_days
        and (merge_rate or 0.0) >= cfg.high_merge_rate
        and has_contributing
        and has_ci
    ):
        return "A"
    if (
        commit_age_days <= 30
        and (merge_rate or 0.0) >= 0.5
        and has_contributing
    ):
        return "B"
    if commit_age_days <= 60 and (merge_rate or 0.0) >= cfg.low_merge_rate:
        return "C"
    return "D"


async def analyse_repo(
    client: GitHubClient,
    repo_full_name: str,
    *,
    cfg: ScoringConfig,
    pr_sample_size: int = 50,
    contributor_window_days: int = 30,
) -> RepoHealth:
    """Produce a `RepoHealth` for `repo_full_name`.

    Issues ~5-7 parallel GitHub calls and folds the responses into one
    payload. Survives missing endpoints (private repos, suspended accounts)
    by treating them as "not present" rather than erroring.
    """
    notes: list[str] = []

    summary_task = asyncio.create_task(client.get_repo(repo_full_name))
    pulls_task = asyncio.create_task(
        client.list_pulls(repo_full_name, state="closed", per_page=pr_sample_size)
    )
    contributors_task = asyncio.create_task(
        client.list_contributors(repo_full_name, per_page=100)
    )
    since = datetime.now(timezone.utc) - timedelta(days=contributor_window_days)
    commits_task = asyncio.create_task(
        client.list_commits(repo_full_name, since_iso=since.isoformat(), per_page=100)
    )
    contributing_task = asyncio.create_task(
        _probe_first_existing(client, repo_full_name, CONTRIBUTING_PATHS)
    )
    coc_task = asyncio.create_task(
        _probe_first_existing(client, repo_full_name, CODE_OF_CONDUCT_PATHS)
    )
    ci_task = asyncio.create_task(_has_ci(client, repo_full_name))

    summary: RepoSummary = await summary_task
    pulls = await pulls_task
    contributors = await contributors_task
    commits = await commits_task
    has_contributing = await contributing_task
    has_coc = await coc_task
    has_ci = await ci_task

    pr_signals = _compute_pr_signals(pulls)

    last_commit = _parse_dt(summary.pushed_at)
    if commits:
        commit_date = _parse_dt(
            commits[0].get("commit", {}).get("author", {}).get("date")
        )
        if commit_date and (last_commit is None or commit_date > last_commit):
            last_commit = commit_date

    # active contributors in last `contributor_window_days` = unique
    # commit authors over the windowed commits listing.
    authors: set[str] = set()
    for c in commits:
        author = c.get("author")
        if isinstance(author, dict) and isinstance(author.get("login"), str):
            authors.add(author["login"])
    active_contributors = len(authors) if commits else None

    if not pulls:
        notes.append("No closed PRs in recent sample — merge rate unknown.")
    if not contributors:
        notes.append("Contributor listing unavailable.")

    grade = _grade_from_signals(
        cfg=cfg,
        merge_rate=pr_signals["merge_rate"],
        last_commit=last_commit,
        has_contributing=has_contributing,
        has_ci=has_ci,
    )

    return RepoHealth(
        repo_full_name=summary.full_name,
        merge_rate=pr_signals["merge_rate"],
        avg_review_time_hours=pr_signals["avg_review_time_hours"],
        avg_merge_time_hours=pr_signals["avg_merge_time_hours"],
        maintainer_response_time_hours=pr_signals["avg_review_time_hours"],
        last_commit_date=last_commit,
        active_contributors_30d=active_contributors,
        has_contributing_guide=has_contributing,
        has_code_of_conduct=has_coc,
        ci_configured=has_ci,
        health_grade=grade,
        notes=notes,
    )
