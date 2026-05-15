"""End-to-end test of the find_issues handler with scoring enabled.

Mocks every endpoint the handler touches so the test runs offline.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from gfi_scout.services.github_api import GitHubClient
from gfi_scout.services.scoring_config import get_scoring_config
from gfi_scout.tools.find_issues import find_issues


def _iso(days_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


@pytest.mark.asyncio
async def test_find_issues_ranks_by_beginner_score(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    # Two repos: one healthy (acme/great), one dead (ghost/town).
    search_payload = {
        "total_count": 2,
        "incomplete_results": False,
        "items": [
            {
                "title": "Fix typo",
                "html_url": "https://github.com/ghost/town/issues/1",
                "body": "tiny",
                "repository_url": "https://api.github.com/repos/ghost/town",
                "labels": [{"name": "good first issue"}],
                "assignee": None,
                "assignees": [],
                "created_at": _iso(200),
                "updated_at": _iso(200),
            },
            {
                "title": "Add type hints",
                "html_url": "https://github.com/acme/great/issues/2",
                "body": "Please add type hints to widgets/utils.py.\n\n"
                "Steps to reproduce:\n```\nrun mypy\n```\n" + ("x" * 400),
                "repository_url": "https://api.github.com/repos/acme/great",
                "labels": [{"name": "good first issue"}],
                "assignee": None,
                "assignees": [],
                "created_at": _iso(3),
                "updated_at": _iso(1),
            },
        ],
    }
    respx_mock.get("/search/issues").mock(return_value=httpx.Response(200, json=search_payload))

    # Healthy repo
    great = "acme/great"
    respx_mock.get(f"/repos/{great}").mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": great,
                "stargazers_count": 5000,
                "language": "Python",
                "pushed_at": _iso(0),
                "topics": [],
            },
        )
    )
    respx_mock.get(f"/repos/{great}/pulls").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"merged_at": _iso(1), "created_at": _iso(2), "updated_at": _iso(1)},
                {"merged_at": _iso(3), "created_at": _iso(5), "updated_at": _iso(3)},
                {"merged_at": _iso(4), "created_at": _iso(6), "updated_at": _iso(4)},
            ],
        )
    )
    respx_mock.get(f"/repos/{great}/contributors").mock(
        return_value=httpx.Response(200, json=[{"login": "a"}, {"login": "b"}])
    )
    respx_mock.get(f"/repos/{great}/commits").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"author": {"login": "a"}, "commit": {"author": {"date": _iso(0)}}},
            ],
        )
    )
    for p, status in (
        ("CONTRIBUTING.md", 200),
        ("docs/CONTRIBUTING.md", 404),
        (".github/CONTRIBUTING.md", 404),
        ("CODE_OF_CONDUCT.md", 200),
        ("docs/CODE_OF_CONDUCT.md", 404),
        (".github/CODE_OF_CONDUCT.md", 404),
        (".github/workflows", 200),
        (".circleci/config.yml", 404),
        (".travis.yml", 404),
        ("azure-pipelines.yml", 404),
        (".gitlab-ci.yml", 404),
    ):
        body = {"name": p} if status == 200 else None
        respx_mock.get(f"/repos/{great}/contents/{p}").mock(
            return_value=httpx.Response(status, json=body)
        )

    # Dead repo
    town = "ghost/town"
    respx_mock.get(f"/repos/{town}").mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": town,
                "stargazers_count": 12,
                "pushed_at": _iso(500),
                "topics": [],
            },
        )
    )
    respx_mock.get(f"/repos/{town}/pulls").mock(return_value=httpx.Response(200, json=[]))
    respx_mock.get(f"/repos/{town}/contributors").mock(return_value=httpx.Response(200, json=[]))
    respx_mock.get(f"/repos/{town}/commits").mock(return_value=httpx.Response(200, json=[]))
    for p in (
        "CONTRIBUTING.md",
        "docs/CONTRIBUTING.md",
        ".github/CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "docs/CODE_OF_CONDUCT.md",
        ".github/CODE_OF_CONDUCT.md",
        ".github/workflows",
        ".circleci/config.yml",
        ".travis.yml",
        "azure-pipelines.yml",
        ".gitlab-ci.yml",
    ):
        respx_mock.get(f"/repos/{town}/contents/{p}").mock(return_value=httpx.Response(404))

    cfg = get_scoring_config()
    results = await find_issues(
        github_client,
        language="python",
        cfg=cfg,
        max_results=10,
        sort_by="beginner_score",
    )

    assert len(results) == 2
    # Healthy repo's issue should win.
    assert results[0].repo_full_name == great
    assert results[0].repo_health_grade == "A"
    assert results[0].beginner_score is not None
    assert results[0].beginner_score > (results[1].beginner_score or 0)
    assert results[1].repo_health_grade == "F"
    assert results[0].freshness == "fresh"
    assert results[1].freshness == "stale"
