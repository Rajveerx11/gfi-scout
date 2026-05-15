"""`check_issue_status` MCP tool."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from gfi_scout.models.issue import IssueStatus
from gfi_scout.services.github_api import GitHubClient
from gfi_scout.services.scoring_config import ScoringConfig
from gfi_scout.utils.logger import get_logger
from gfi_scout.utils.validators import parse_issue_url

log = get_logger(__name__)

MAINTAINER_ASSOC = {"OWNER", "MEMBER", "COLLABORATOR"}
LINKED_PR_RE = re.compile(
    r"\b(closes|fixes|resolves)\s+#(\d+)\b", re.IGNORECASE,
)


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _verdict(
    *,
    is_assigned: bool,
    has_linked_pr: bool,
    is_stale: bool,
    competitor_prs: int,
) -> str:
    if is_assigned or has_linked_pr or competitor_prs > 0:
        return "LIKELY_TAKEN"
    if is_stale:
        return "STALE"
    return "AVAILABLE"


async def check_issue_status(
    client: GitHubClient,
    issue_url: str,
    *,
    cfg: ScoringConfig,
) -> IssueStatus:
    """Check whether an issue is actually available to work on."""
    repo, number = parse_issue_url(issue_url)
    log.info("check_issue_status repo=%s number=%s", repo, number)

    issue = await client.get_issue(repo, number)
    comments = await client.list_issue_comments(repo, number)
    timeline = await client.list_issue_timeline(repo, number)

    is_assigned = issue.assignee is not None or len(issue.assignees) > 0

    has_linked_pr = False
    competitor_prs = 0
    for event in timeline:
        ev = event.get("event") if isinstance(event, dict) else None
        if ev == "cross-referenced":
            source = event.get("source", {}) if isinstance(event, dict) else {}
            issue_obj = source.get("issue") if isinstance(source, dict) else None
            if isinstance(issue_obj, dict) and issue_obj.get("pull_request"):
                state = issue_obj.get("state")
                if state == "open":
                    competitor_prs += 1
                has_linked_pr = has_linked_pr or state == "open"
        elif ev == "connected":
            has_linked_pr = True

    if not has_linked_pr:
        for comment in comments:
            body = comment.get("body") if isinstance(comment, dict) else None
            if isinstance(body, str) and LINKED_PR_RE.search(body):
                has_linked_pr = True
                break

    last_activity = _parse_dt(issue.updated_at)
    for comment in comments:
        ts = _parse_dt(comment.get("updated_at") or comment.get("created_at"))
        if ts and (last_activity is None or ts > last_activity):
            last_activity = ts

    if last_activity is None:
        is_stale = True
    else:
        age_days = (datetime.now(timezone.utc) - last_activity).days
        is_stale = age_days >= cfg.stale_issue_days

    maintainer_confirmed = False
    for comment in comments:
        assoc = comment.get("author_association") if isinstance(comment, dict) else None
        if isinstance(assoc, str) and assoc in MAINTAINER_ASSOC:
            maintainer_confirmed = True
            break

    notes: list[str] = []
    if not comments:
        notes.append("No comments on this issue.")
    if competitor_prs > 1:
        notes.append(f"{competitor_prs} open PRs reference this issue.")

    return IssueStatus(
        issue_url=issue.html_url,
        is_assigned=is_assigned,
        has_linked_pr=has_linked_pr,
        last_activity=last_activity,
        is_stale=is_stale,
        competitor_prs=competitor_prs,
        maintainer_confirmed=maintainer_confirmed,
        availability_verdict=_verdict(
            is_assigned=is_assigned,
            has_linked_pr=has_linked_pr,
            is_stale=is_stale,
            competitor_prs=competitor_prs,
        ),
        notes=notes,
    )
