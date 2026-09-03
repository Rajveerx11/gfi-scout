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
    assert status.claim_detected is False


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
async def test_maintainer_comment_without_confirmation_stays_available(
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
    assert status.claim_detected is False
    assert status.maintainer_confirmed is False
    assert status.availability_verdict == "AVAILABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fixture_key", "claim_detected", "maintainer_confirmed", "verdict"),
    [
        ("confirmed_claim", True, True, "LIKELY_TAKEN"),
        ("claim_without_confirmation", True, False, "AVAILABLE"),
        ("confirmation_without_claim", False, False, "AVAILABLE"),
        ("old_confirmation_then_claim", True, False, "AVAILABLE"),
        ("confirmation_for_different_claimant", True, False, "AVAILABLE"),
        ("negated_confirmation", True, False, "AVAILABLE"),
        ("quoted_confirmation", True, False, "AVAILABLE"),
        ("question_confirmation", True, False, "AVAILABLE"),
        ("confirmation_then_separate_question", True, True, "LIKELY_TAKEN"),
        ("confirmation_then_retraction", True, False, "AVAILABLE"),
        ("confirmation_then_later_retraction", True, False, "AVAILABLE"),
        ("confirmation_then_retraction_question", True, True, "LIKELY_TAKEN"),
        ("cross_claimant_retraction", True, True, "LIKELY_TAKEN"),
        ("confirmed_claimant_retracted", True, False, "AVAILABLE"),
        ("unmentioned_stance_targets_latest_claimant", True, False, "AVAILABLE"),
        ("mixed_directed_stances", True, True, "LIKELY_TAKEN"),
        ("quoted_mention_does_not_redirect_stance", True, False, "AVAILABLE"),
        ("anonymous_claim_confirmed", True, True, "LIKELY_TAKEN"),
        ("anonymous_claim_retracted", True, False, "AVAILABLE"),
        ("named_then_anonymous_claim", True, True, "LIKELY_TAKEN"),
    ],
)
async def test_claim_detection_from_fixture_comments(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
    issue_comments: dict[str, list[dict[str, object]]],
    fixture_key: str,
    claim_detected: bool,
    maintainer_confirmed: bool,
    verdict: str,
) -> None:
    repo = "acme/widgets"
    url = "https://github.com/acme/widgets/issues/11"
    respx_mock.get(f"/repos/{repo}/issues/11").mock(
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
                "comments": 2,
            },
        )
    )
    respx_mock.get(f"/repos/{repo}/issues/11/comments").mock(
        return_value=httpx.Response(200, json=issue_comments[fixture_key])
    )
    respx_mock.get(f"/repos/{repo}/issues/11/timeline").mock(
        return_value=httpx.Response(200, json=[])
    )

    status = await check_issue_status(github_client, url, cfg=get_scoring_config())

    assert status.claim_detected is claim_detected
    assert status.maintainer_confirmed is maintainer_confirmed
    assert status.availability_verdict == verdict
