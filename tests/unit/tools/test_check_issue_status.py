from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from gfi_scout.services.github_api import GitHubClient
from gfi_scout.services.scoring_config import get_scoring_config
from gfi_scout.tools.check_issue_status import check_issue_status


def _iso(days_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


@pytest.mark.asyncio
async def test_available_when_unassigned_fresh_no_links(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    repo = "acme/widgets"
    url = "https://github.com/acme/widgets/issues/42"
    respx_mock.get(f"/repos/{repo}/issues/42").mock(
        return_value=httpx.Response(
            200,
            json={
                "title": "fix this",
                "html_url": url,
                "body": "describe the bug",
                "repository_url": f"https://api.github.com/repos/{repo}",
                "labels": [{"name": "good first issue"}],
                "assignee": None,
                "assignees": [],
                "created_at": _iso(2),
                "updated_at": _iso(1),
            },
        )
    )
    respx_mock.get(f"/repos/{repo}/issues/42/comments").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx_mock.get(f"/repos/{repo}/issues/42/timeline").mock(
        return_value=httpx.Response(200, json=[])
    )

    cfg = get_scoring_config()
    status = await check_issue_status(github_client, url, cfg=cfg)
    assert status.availability_verdict == "AVAILABLE"
    assert status.is_assigned is False
    assert status.has_linked_pr is False
    assert status.competitor_prs == 0


@pytest.mark.asyncio
async def test_likely_taken_when_competitor_pr_open(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    repo = "acme/widgets"
    url = "https://github.com/acme/widgets/issues/9"
    respx_mock.get(f"/repos/{repo}/issues/9").mock(
        return_value=httpx.Response(
            200,
            json={
                "title": "x",
                "html_url": url,
                "body": "",
                "repository_url": f"https://api.github.com/repos/{repo}",
                "labels": [],
                "assignee": None,
                "assignees": [],
                "created_at": _iso(3),
                "updated_at": _iso(1),
            },
        )
    )
    respx_mock.get(f"/repos/{repo}/issues/9/comments").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "body": "Closes #9 in #50",
                    "updated_at": _iso(0),
                    "author_association": "CONTRIBUTOR",
                },
            ],
        )
    )
    respx_mock.get(f"/repos/{repo}/issues/9/timeline").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "event": "cross-referenced",
                    "source": {
                        "issue": {
                            "state": "open",
                            "pull_request": {
                                "url": "https://api.github.com/repos/acme/widgets/pulls/50"
                            },
                        }
                    },
                },
            ],
        )
    )
    cfg = get_scoring_config()
    status = await check_issue_status(github_client, url, cfg=cfg)
    assert status.has_linked_pr is True
    assert status.competitor_prs == 1
    assert status.availability_verdict == "LIKELY_TAKEN"


@pytest.mark.asyncio
async def test_stale_when_no_recent_activity(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    repo = "acme/widgets"
    url = "https://github.com/acme/widgets/issues/100"
    respx_mock.get(f"/repos/{repo}/issues/100").mock(
        return_value=httpx.Response(
            200,
            json={
                "title": "x",
                "html_url": url,
                "body": "",
                "repository_url": f"https://api.github.com/repos/{repo}",
                "labels": [],
                "assignee": None,
                "assignees": [],
                "created_at": _iso(400),
                "updated_at": _iso(200),
            },
        )
    )
    respx_mock.get(f"/repos/{repo}/issues/100/comments").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx_mock.get(f"/repos/{repo}/issues/100/timeline").mock(
        return_value=httpx.Response(200, json=[])
    )
    cfg = get_scoring_config()
    status = await check_issue_status(github_client, url, cfg=cfg)
    assert status.is_stale is True
    assert status.availability_verdict == "STALE"


@pytest.mark.asyncio
async def test_maintainer_confirmed_when_owner_comments(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    repo = "acme/widgets"
    url = "https://github.com/acme/widgets/issues/3"
    respx_mock.get(f"/repos/{repo}/issues/3").mock(
        return_value=httpx.Response(
            200,
            json={
                "title": "x",
                "html_url": url,
                "body": "describe",
                "repository_url": f"https://api.github.com/repos/{repo}",
                "labels": [],
                "assignee": None,
                "assignees": [],
                "created_at": _iso(2),
                "updated_at": _iso(1),
            },
        )
    )
    respx_mock.get(f"/repos/{repo}/issues/3/comments").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "body": "good call, PRs welcome",
                    "updated_at": _iso(1),
                    "author_association": "OWNER",
                },
            ],
        )
    )
    respx_mock.get(f"/repos/{repo}/issues/3/timeline").mock(
        return_value=httpx.Response(200, json=[])
    )
    cfg = get_scoring_config()
    status = await check_issue_status(github_client, url, cfg=cfg)
    assert status.maintainer_confirmed is True
    assert status.availability_verdict == "AVAILABLE"
