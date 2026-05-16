"""FastMCP server entry point. Registers all GFI Scout tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from gfi_scout.config import load_settings
from gfi_scout.models.issue import ContributionGuide, IssueResult, IssueStatus
from gfi_scout.models.repo import RepoHealth
from gfi_scout.runtime import make_client
from gfi_scout.services.scoring_config import get_scoring_config
from gfi_scout.tools.check_issue_status import (
    check_issue_status as _check_issue_status_impl,
)
from gfi_scout.tools.check_repo_health import (
    check_repo_health as _check_repo_health_impl,
)
from gfi_scout.tools.find_issues import find_issues as _find_issues_impl
from gfi_scout.tools.get_contribution_guide import (
    get_contribution_guide as _get_contribution_guide_impl,
)
from gfi_scout.utils.logger import get_logger

mcp = FastMCP("gfi-scout")
log = get_logger(__name__)


@mcp.tool()
async def find_issues(
    language: str,
    min_stars: int = 50,
    max_stars: int = 50000,
    labels: list[str] | None = None,
    max_results: int = 10,
    sort_by: str = "beginner_score",
    topic: str | None = None,
    unassigned_only: bool = True,
) -> list[IssueResult]:
    """Find beginner-friendly open source issues ranked by likelihood of success.

    Searches GitHub for "good first issue" labelled issues, scores each by
    repo health + freshness + clarity + merge friendliness + setup ease,
    and returns the top results.

    Args:
        language: Programming language (e.g. "python", "typescript").
        min_stars: Minimum repo stars. Default 50.
        max_stars: Maximum repo stars. Default 50000.
        labels: Issue labels to require. Default ["good first issue"].
        max_results: How many results (1-25).
        sort_by: "beginner_score" | "freshness" | "repo_health".
        topic: Optional GitHub topic filter ("web", "cli", "data-science", ...).
        unassigned_only: When True (default), excludes issues that already
            have an assignee. Set False to widen the search when narrow
            language/label/stars combos return zero hits.
    """
    cfg = get_scoring_config()
    settings = load_settings()
    async with make_client(settings) as client:
        return await _find_issues_impl(
            client,
            language=language,
            cfg=cfg,
            min_stars=min_stars,
            max_stars=max_stars,
            labels=labels,
            max_results=max_results,
            sort_by=sort_by,
            topic=topic,
            unassigned_only=unassigned_only,
            health_concurrency=settings.max_concurrent_requests,
        )


@mcp.tool()
async def check_repo_health(repo: str) -> RepoHealth:
    """Analyse a repository's contributor-friendliness.

    Args:
        repo: Full repo name, e.g. "fastapi/fastapi".
    """
    cfg = get_scoring_config()
    async with make_client() as client:
        return await _check_repo_health_impl(client, repo, cfg=cfg)


@mcp.tool()
async def check_issue_status(issue_url: str) -> IssueStatus:
    """Check whether a specific GitHub issue is actually available to work on.

    Args:
        issue_url: Full GitHub issue URL.
    """
    cfg = get_scoring_config()
    async with make_client() as client:
        return await _check_issue_status_impl(client, issue_url, cfg=cfg)


@mcp.tool()
async def get_contribution_guide(repo: str) -> ContributionGuide:
    """Pull and summarise a repo's contribution guide + setup instructions.

    Args:
        repo: Full repo name, e.g. "fastapi/fastapi".
    """
    async with make_client() as client:
        return await _get_contribution_guide_impl(client, repo)


def main() -> None:
    """Console-script entry point — runs over stdio for Claude Desktop et al."""
    log.info("Starting gfi-scout MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
