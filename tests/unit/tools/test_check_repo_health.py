from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from gfi_scout.services.github_api import GitHubClient
from gfi_scout.services.scoring_config import get_scoring_config
from gfi_scout.tools.check_repo_health import check_repo_health


def _recent_iso(days_ago: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


@pytest.mark.asyncio
async def test_check_repo_health_happy_path(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    repo = "fastapi/fastapi"
    respx_mock.get(f"/repos/{repo}").mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": repo,
                "stargazers_count": 50000,
                "language": "Python",
                "default_branch": "main",
                "pushed_at": _recent_iso(0),
                "open_issues_count": 100,
                "topics": ["python", "web"],
            },
        )
    )
    respx_mock.get(f"/repos/{repo}/pulls").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "merged_at": _recent_iso(1),
                    "created_at": _recent_iso(3),
                    "updated_at": _recent_iso(1),
                },
                {
                    "merged_at": _recent_iso(2),
                    "created_at": _recent_iso(5),
                    "updated_at": _recent_iso(2),
                },
                {
                    "merged_at": _recent_iso(3),
                    "created_at": _recent_iso(6),
                    "updated_at": _recent_iso(3),
                },
                {
                    "merged_at": _recent_iso(4),
                    "created_at": _recent_iso(7),
                    "updated_at": _recent_iso(4),
                },
                {
                    "merged_at": None,
                    "created_at": _recent_iso(15),
                    "updated_at": _recent_iso(10),
                },
            ],
        )
    )
    respx_mock.get(f"/repos/{repo}/contributors").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"login": "a"},
                {"login": "b"},
                {"login": "c"},
            ],
        )
    )
    respx_mock.get(f"/repos/{repo}/commits").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"author": {"login": "a"}, "commit": {"author": {"date": _recent_iso(1)}}},
                {"author": {"login": "b"}, "commit": {"author": {"date": _recent_iso(2)}}},
            ],
        )
    )
    # CONTRIBUTING.md exists at root
    respx_mock.get(f"/repos/{repo}/contents/CONTRIBUTING.md").mock(
        return_value=httpx.Response(200, json={"name": "CONTRIBUTING.md"})
    )
    # other CONTRIBUTING paths 404
    respx_mock.get(f"/repos/{repo}/contents/docs/CONTRIBUTING.md").mock(
        return_value=httpx.Response(404)
    )
    respx_mock.get(f"/repos/{repo}/contents/.github/CONTRIBUTING.md").mock(
        return_value=httpx.Response(404)
    )
    # CoC found at root
    respx_mock.get(f"/repos/{repo}/contents/CODE_OF_CONDUCT.md").mock(
        return_value=httpx.Response(200, json={"name": "CODE_OF_CONDUCT.md"})
    )
    respx_mock.get(f"/repos/{repo}/contents/docs/CODE_OF_CONDUCT.md").mock(
        return_value=httpx.Response(404)
    )
    respx_mock.get(f"/repos/{repo}/contents/.github/CODE_OF_CONDUCT.md").mock(
        return_value=httpx.Response(404)
    )
    # CI: workflows directory exists
    respx_mock.get(f"/repos/{repo}/contents/.github/workflows").mock(
        return_value=httpx.Response(200, json=[{"name": "ci.yml"}])
    )
    respx_mock.get(f"/repos/{repo}/contents/.circleci/config.yml").mock(
        return_value=httpx.Response(404)
    )
    respx_mock.get(f"/repos/{repo}/contents/.travis.yml").mock(return_value=httpx.Response(404))
    respx_mock.get(f"/repos/{repo}/contents/azure-pipelines.yml").mock(
        return_value=httpx.Response(404)
    )
    respx_mock.get(f"/repos/{repo}/contents/.gitlab-ci.yml").mock(return_value=httpx.Response(404))

    cfg = get_scoring_config()
    result = await check_repo_health(github_client, repo, cfg=cfg)

    assert result.repo_full_name == repo
    assert result.merge_rate is not None
    assert 0.5 < result.merge_rate <= 1.0
    assert result.has_contributing_guide is True
    assert result.has_code_of_conduct is True
    assert result.ci_configured is True
    assert result.health_grade == "A"
    assert result.active_contributors_30d == 2


@pytest.mark.asyncio
async def test_check_repo_health_dead_repo_gets_f(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    repo = "ghost/town"
    old = (datetime.now(UTC) - timedelta(days=400)).isoformat()
    respx_mock.get(f"/repos/{repo}").mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": repo,
                "stargazers_count": 12,
                "pushed_at": old,
                "topics": [],
            },
        )
    )
    respx_mock.get(f"/repos/{repo}/pulls").mock(return_value=httpx.Response(200, json=[]))
    respx_mock.get(f"/repos/{repo}/contributors").mock(return_value=httpx.Response(200, json=[]))
    respx_mock.get(f"/repos/{repo}/commits").mock(return_value=httpx.Response(200, json=[]))
    for path in (
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
        respx_mock.get(f"/repos/{repo}/contents/{path}").mock(return_value=httpx.Response(404))

    cfg = get_scoring_config()
    result = await check_repo_health(github_client, repo, cfg=cfg)
    assert result.health_grade == "F"
    assert result.has_contributing_guide is False
    assert result.ci_configured is False
