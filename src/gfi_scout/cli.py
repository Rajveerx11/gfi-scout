"""Standalone command-line and interactive terminal UI for GFI Scout."""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from typing import Any, Literal, cast

from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from gfi_scout.config import ConfigError, load_settings
from gfi_scout.models.issue import ContributionGuide, IssueResult, IssueStatus
from gfi_scout.models.repo import RepoHealth
from gfi_scout.runtime import make_client
from gfi_scout.services.github_api import GitHubAPIError
from gfi_scout.services.scoring_config import get_scoring_config
from gfi_scout.tools.check_issue_status import check_issue_status
from gfi_scout.tools.check_repo_health import check_repo_health
from gfi_scout.tools.find_issues import find_issues
from gfi_scout.tools.get_contribution_guide import get_contribution_guide
from gfi_scout.utils.validators import ValidationError

OutputFormat = Literal["table", "json"]
CommandRunner = Callable[[argparse.Namespace], Awaitable[int]]

console = Console()
error_console = Console(stderr=True)


def _split_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    values = [part.strip() for part in value.split(",") if part.strip()]
    return values or None


def _jsonable(payload: BaseModel | Sequence[BaseModel]) -> dict[str, Any] | list[dict[str, Any]]:
    if isinstance(payload, BaseModel):
        return dict(payload.model_dump(mode="json"))
    return [dict(item.model_dump(mode="json")) for item in payload]


def print_json(payload: BaseModel | Sequence[BaseModel], *, out: Console = console) -> None:
    """Print a Pydantic payload as deterministic JSON."""
    out.file.write(json.dumps(_jsonable(payload), indent=2, sort_keys=True))
    out.file.write("\n")
    out.file.flush()


def _date(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.date().isoformat()


def _score(value: int | None) -> str:
    return "-" if value is None else str(value)


def _labels(labels: list[str]) -> str:
    if not labels:
        return "-"
    joined = ", ".join(labels)
    return joined if len(joined) <= 38 else joined[:35].rstrip() + "..."


def render_issues(results: list[IssueResult], *, out: Console = console) -> None:
    """Render issue search results as a compact terminal table."""
    if not results:
        out.print("[yellow]No matching issues found.[/yellow]")
        return

    table = Table(title="GFI Scout Issues", show_lines=False)
    table.add_column("Score", justify="right", no_wrap=True)
    table.add_column("Grade", no_wrap=True)
    table.add_column("Fresh", no_wrap=True)
    table.add_column("Repo", overflow="fold")
    table.add_column("Title", overflow="fold")
    table.add_column("Labels", overflow="fold")
    table.add_column("URL", overflow="fold")

    for issue in results:
        table.add_row(
            _score(issue.beginner_score),
            issue.repo_health_grade or "-",
            issue.freshness or "-",
            issue.repo_full_name,
            issue.title,
            _labels(issue.labels),
            str(issue.url),
        )
    out.print(table)


def render_health(health: RepoHealth, *, out: Console = console) -> None:
    table = Table(title=f"Repository Health: {health.repo_full_name}", show_lines=False)
    table.add_column("Signal")
    table.add_column("Value")
    table.add_row("Health grade", health.health_grade)
    table.add_row(
        "Merge rate",
        "-" if health.merge_rate is None else f"{health.merge_rate * 100:.1f}%",
    )
    table.add_row("Avg review time", _hours(health.avg_review_time_hours))
    table.add_row("Avg merge time", _hours(health.avg_merge_time_hours))
    table.add_row("Last commit", _date(health.last_commit_date))
    table.add_row(
        "Active contributors 30d",
        "-" if health.active_contributors_30d is None else str(health.active_contributors_30d),
    )
    table.add_row("CONTRIBUTING", "yes" if health.has_contributing_guide else "no")
    table.add_row("Code of Conduct", "yes" if health.has_code_of_conduct else "no")
    table.add_row("CI configured", "yes" if health.ci_configured else "no")
    out.print(table)
    if health.notes:
        out.print(Panel("\n".join(health.notes), title="Notes"))


def _hours(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}h"


def render_status(status: IssueStatus, *, out: Console = console) -> None:
    table = Table(title="Issue Status", show_lines=False)
    table.add_column("Signal")
    table.add_column("Value")
    table.add_row("Verdict", status.availability_verdict)
    table.add_row("Assigned", "yes" if status.is_assigned else "no")
    table.add_row("Linked PR", "yes" if status.has_linked_pr else "no")
    table.add_row("Competitor PRs", str(status.competitor_prs))
    table.add_row("Maintainer confirmed", "yes" if status.maintainer_confirmed else "no")
    table.add_row("Stale", "yes" if status.is_stale else "no")
    table.add_row("Last activity", _date(status.last_activity))
    table.add_row("URL", str(status.issue_url))
    out.print(table)
    if status.notes:
        out.print(Panel("\n".join(status.notes), title="Notes"))


def render_guide(guide: ContributionGuide, *, out: Console = console) -> None:
    out.print(
        Panel(
            guide.contributing_summary or "No contribution guide text found.",
            title=guide.repo_full_name,
        )
    )
    table = Table(title="Contribution Guide", show_lines=False)
    table.add_column("Section")
    table.add_column("Details", overflow="fold")
    table.add_row("Setup complexity", guide.setup_complexity)
    table.add_row("Required tools", ", ".join(guide.required_tools) or "-")
    table.add_row("Source files", ", ".join(guide.source_files) or "-")
    table.add_row("Setup", _bullet_block(guide.setup_instructions))
    table.add_row("Tests", _bullet_block(guide.testing_requirements))
    table.add_row("PR conventions", _bullet_block(guide.pr_conventions))
    out.print(table)


def _bullet_block(items: list[str]) -> str:
    if not items:
        return "-"
    return "\n".join(f"- {item}" for item in items)


async def run_find(args: argparse.Namespace, *, out: Console = console) -> int:
    settings = load_settings()
    if settings.github_token is None:
        error_console.print(
            "[dim]Running unauthenticated (60 req/h) — set GITHUB_TOKEN for 5,000 req/h.[/dim]"
        )
    cfg = get_scoring_config()
    labels = _split_csv(cast(str | None, args.labels))
    async with make_client(settings) as client:
        results = await find_issues(
            client,
            language=cast(str, args.language),
            cfg=cfg,
            min_stars=cast(int, args.min_stars),
            max_stars=cast(int, args.max_stars),
            labels=labels,
            max_results=cast(int, args.max_results),
            sort_by=cast(str, args.sort_by),
            topic=cast(str | None, args.topic),
            unassigned_only=not cast(bool, args.include_assigned),
            enable_scoring=not cast(bool, args.no_scoring),
            health_concurrency=settings.max_concurrent_requests,
        )
    if cast(OutputFormat, args.output) == "json":
        print_json(results, out=out)
    else:
        render_issues(results, out=out)
    return 0

async def run_health(args: argparse.Namespace, *, out: Console = console) -> int:
    cfg = get_scoring_config()
    async with make_client() as client:
        health = await check_repo_health(client, cast(str, args.repo), cfg=cfg)
    if cast(OutputFormat, args.output) == "json":
        print_json(health, out=out)
    else:
        render_health(health, out=out)
    return 0


async def run_status(args: argparse.Namespace, *, out: Console = console) -> int:
    cfg = get_scoring_config()
    async with make_client() as client:
        status = await check_issue_status(client, cast(str, args.issue_url), cfg=cfg)
    if cast(OutputFormat, args.output) == "json":
        print_json(status, out=out)
    else:
        render_status(status, out=out)
    return 0


async def run_guide(args: argparse.Namespace, *, out: Console = console) -> int:
    async with make_client() as client:
        guide = await get_contribution_guide(client, cast(str, args.repo))
    if cast(OutputFormat, args.output) == "json":
        print_json(guide, out=out)
    else:
        render_guide(guide, out=out)
    return 0


async def run_tui(args: argparse.Namespace, *, out: Console = console) -> int:  # noqa: ARG001
    out.print(Panel("Search and inspect beginner-friendly open source issues.", title="GFI Scout"))
    while True:
        out.print()
        out.print("[bold]1[/bold] Find issues")
        out.print("[bold]2[/bold] Check repo health")
        out.print("[bold]3[/bold] Check issue status")
        out.print("[bold]4[/bold] Get contribution guide")
        out.print("[bold]q[/bold] Quit")
        choice = Prompt.ask("Choose", choices=["1", "2", "3", "4", "q"], default="1")
        if choice == "q":
            return 0
        try:
            if choice == "1":
                await _tui_find(out=out)
            elif choice == "2":
                await _tui_health(out=out)
            elif choice == "3":
                await _tui_status(out=out)
            elif choice == "4":
                await _tui_guide(out=out)
        except (ConfigError, GitHubAPIError, ValidationError, ValueError) as exc:
            error_console.print(f"[red]{exc}[/red]")
        if not Confirm.ask("Run another action?", default=True):
            return 0


async def _tui_find(*, out: Console) -> None:
    language = Prompt.ask("Language", default="python")
    min_stars = IntPrompt.ask("Minimum stars", default=50)
    max_stars = IntPrompt.ask("Maximum stars", default=50000)
    max_results = IntPrompt.ask("Max results", default=10)
    topic = Prompt.ask("Topic filter (blank for none)", default="").strip() or None
    labels = _split_csv(Prompt.ask("Labels, comma-separated", default="good first issue"))
    include_assigned = Confirm.ask("Include assigned issues?", default=False)
    args = argparse.Namespace(
        language=language,
        min_stars=min_stars,
        max_stars=max_stars,
        max_results=max_results,
        topic=topic,
        labels=",".join(labels or []) if labels else None,
        include_assigned=include_assigned,
        no_scoring=False,
        sort_by="beginner_score",
        output="table",
    )
    await run_find(args, out=out)


async def _tui_health(*, out: Console) -> None:
    repo = Prompt.ask("Repository", default="fastapi/fastapi")
    args = argparse.Namespace(repo=repo, output="table")
    await run_health(args, out=out)


async def _tui_status(*, out: Console) -> None:
    issue_url = Prompt.ask("Issue URL")
    args = argparse.Namespace(issue_url=issue_url, output="table")
    await run_status(args, out=out)


async def _tui_guide(*, out: Console) -> None:
    repo = Prompt.ask("Repository", default="fastapi/fastapi")
    args = argparse.Namespace(repo=repo, output="table")
    await run_guide(args, out=out)


def _add_output_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output",
        choices=("table", "json"),
        default="table",
        help="Output format.",
    )


def _package_version() -> str:
    try:
        return importlib.metadata.version("gfi-scout")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gfi-scout-cli",
        description="Standalone CLI and terminal UI for GFI Scout.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"gfi-scout {_package_version()}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    find_parser = subparsers.add_parser("find", help="Find ranked beginner-friendly issues.")
    find_parser.add_argument("language", help='Programming language, e.g. "python".')
    find_parser.add_argument("--min-stars", type=int, default=50)
    find_parser.add_argument("--max-stars", type=int, default=50000)
    find_parser.add_argument("--max-results", type=int, default=10)
    find_parser.add_argument("--label", dest="labels", help="Comma-separated labels.")
    find_parser.add_argument("--topic", help="GitHub topic filter.")
    find_parser.add_argument(
        "--sort-by",
        choices=("beginner_score", "freshness", "repo_health"),
        default="beginner_score",
    )
    find_parser.add_argument(
        "--include-assigned",
        action="store_true",
        help="Include issues that already have an assignee.",
    )
    find_parser.add_argument(
        "--no-scoring",
        action="store_true",
        help="Skip repo-health fan-out and return raw search results.",
    )
    _add_output_arg(find_parser)
    find_parser.set_defaults(runner=run_find)

    health_parser = subparsers.add_parser("health", help="Check repository contributor health.")
    health_parser.add_argument("repo", help='Repository as "owner/name" or a GitHub URL.')
    _add_output_arg(health_parser)
    health_parser.set_defaults(runner=run_health)

    status_parser = subparsers.add_parser("status", help="Check whether an issue is available.")
    status_parser.add_argument("issue_url", help="Full GitHub issue URL.")
    _add_output_arg(status_parser)
    status_parser.set_defaults(runner=run_status)

    guide_parser = subparsers.add_parser("guide", help="Summarise contribution instructions.")
    guide_parser.add_argument("repo", help='Repository as "owner/name" or a GitHub URL.')
    _add_output_arg(guide_parser)
    guide_parser.set_defaults(runner=run_guide)

    tui_parser = subparsers.add_parser("tui", help="Open the interactive terminal UI.")
    tui_parser.set_defaults(runner=run_tui)
    return parser


async def _dispatch(args: argparse.Namespace) -> int:
    runner = cast(CommandRunner | None, getattr(args, "runner", None))
    if runner is None:
        raise ValueError("No command selected")
    return await runner(args)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_dispatch(args))
    except (ConfigError, GitHubAPIError, ValidationError, ValueError) as exc:
        error_console.print(Text(str(exc), style="red"))
        return 1


def tui_main() -> int:
    return main(["tui"])


if __name__ == "__main__":
    raise SystemExit(main())
