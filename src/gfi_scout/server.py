"""FastMCP server entry point. Registers all GFI Scout tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from gfi_scout.config import load_settings
from gfi_scout.models.issue import IssueResult
from gfi_scout.services.github_api import GitHubClient
from gfi_scout.tools.find_issues import find_issues as _find_issues_impl
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
) -> list[IssueResult]:
    """Find beginner-friendly open source issues ranked by likelihood of success.

    Searches GitHub for "good first issue" labelled issues filtered by language
    and star range, returning title, URL, body preview, repository, labels and
    assignment status. Smart scoring lands in Phase 2.

    Args:
        language: Programming language to filter by (e.g. "python", "typescript").
        min_stars: Minimum repo stars. Default 50.
        max_stars: Maximum repo stars. Default 50000.
        labels: Issue labels to require. Default ["good first issue"].
        max_results: How many results to return (1-25).
        sort_by: Accepted but not yet honoured in Phase 1.
        topic: Optional GitHub topic filter (e.g. "web", "cli", "data-science").
    """
    settings = load_settings()
    async with GitHubClient(token=settings.github_token) as client:
        return await _find_issues_impl(
            client,
            language=language,
            min_stars=min_stars,
            max_stars=max_stars,
            labels=labels,
            max_results=max_results,
            sort_by=sort_by,
            topic=topic,
        )


def main() -> None:
    """Console-script entry point — runs over stdio for Claude Desktop et al."""
    log.info("Starting gfi-scout MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
