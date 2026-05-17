from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from gfi_scout.services.github_api import GitHubClient
from gfi_scout.tools.find_issues import (
    BODY_PREVIEW_CHARS,
    build_repo_search_query,
    find_issues,
)


class TestBuildRepoSearchQuery:
    def test_includes_language_and_stars(self) -> None:
        query = build_repo_search_query(
            language="python",
            min_stars=50,
            max_stars=50000,
            topic=None,
        )
        assert "language:python" in query
        assert "stars:50..50000" in query

    def test_appends_topic_when_given(self) -> None:
        query = build_repo_search_query(
            language="python",
            min_stars=50,
            max_stars=50000,
            topic="cli",
        )
        assert "topic:cli" in query

    def test_clamps_negative_and_inverted_star_bounds(self) -> None:
        query = build_repo_search_query(
            language="python",
            min_stars=-100,
            max_stars=-5,
            topic=None,
        )
        assert "stars:0..0" in query


def _repo_search_payload(repos: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_count": len(repos),
        "incomplete_results": False,
        "items": repos,
    }


def _issue(
    *,
    title: str,
    repo: str,
    number: int = 1,
    assigned: bool = False,
    labels: list[str] | None = None,
    body: str = "starter task",
) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    assignee = {"login": "taken-user"} if assigned else None
    return {
        "title": title,
        "html_url": f"https://github.com/{owner}/{name}/issues/{number}",
        "body": body,
        "repository_url": f"https://api.github.com/repos/{repo}",
        "labels": [{"name": lb} for lb in (labels or ["good first issue"])],
        "assignee": assignee,
        "assignees": [assignee] if assignee else [],
        "created_at": "2026-04-01T12:00:00Z",
        "updated_at": "2026-05-10T09:30:00Z",
    }


def _mock_repo_search(
    respx_mock: respx.MockRouter,
    repos: list[dict[str, Any]],
) -> respx.Route:
    return respx_mock.get("/search/repositories").mock(
        return_value=httpx.Response(200, json=_repo_search_payload(repos))
    )


def _mock_repo_issues(
    respx_mock: respx.MockRouter,
    repo: str,
    issues: list[dict[str, Any]],
) -> respx.Route:
    return respx_mock.get(f"/repos/{repo}/issues").mock(
        return_value=httpx.Response(200, json=issues)
    )


@pytest.mark.asyncio
async def test_find_issues_maps_response_to_issue_results(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    repos = [
        {
            "full_name": "acme/widgets",
            "stargazers_count": 1200,
            "language": "Python",
            "topics": [],
        },
        {
            "full_name": "acme/sprockets",
            "stargazers_count": 800,
            "language": "Python",
            "topics": [],
        },
    ]
    _mock_repo_search(respx_mock, repos)
    _mock_repo_issues(
        respx_mock,
        "acme/widgets",
        [_issue(title="Add type hints to utils module", repo="acme/widgets", number=42)],
    )
    _mock_repo_issues(
        respx_mock,
        "acme/sprockets",
        [_issue(title="Fix typo", repo="acme/sprockets", number=7, assigned=True)],
    )

    results = await find_issues(
        github_client,
        language="python",
        max_results=10,
        enable_scoring=False,
        unassigned_only=False,
    )

    assert len(results) == 2
    by_repo = {r.repo_full_name: r for r in results}
    widgets = by_repo["acme/widgets"]
    assert widgets.title == "Add type hints to utils module"
    assert str(widgets.url) == "https://github.com/acme/widgets/issues/42"
    assert "good first issue" in widgets.labels
    assert widgets.is_assigned is False
    assert widgets.repo_stars == 1200
    assert widgets.repo_language == "Python"

    sprockets = by_repo["acme/sprockets"]
    assert sprockets.is_assigned is True


@pytest.mark.asyncio
async def test_find_issues_filters_assigned_by_default(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    _mock_repo_search(
        respx_mock,
        [{"full_name": "acme/sprockets", "stargazers_count": 500, "topics": []}],
    )
    _mock_repo_issues(
        respx_mock,
        "acme/sprockets",
        [
            _issue(title="Taken", repo="acme/sprockets", number=1, assigned=True),
            _issue(title="Free", repo="acme/sprockets", number=2, assigned=False),
        ],
    )

    results = await find_issues(
        github_client,
        language="python",
        enable_scoring=False,
    )

    assert [r.title for r in results] == ["Free"]


@pytest.mark.asyncio
async def test_find_issues_clamps_max_results(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    _mock_repo_search(
        respx_mock,
        [{"full_name": "acme/widgets", "stargazers_count": 1000, "topics": []}],
    )
    _mock_repo_issues(
        respx_mock,
        "acme/widgets",
        [_issue(title=f"Issue {i}", repo="acme/widgets", number=i) for i in range(1, 6)],
    )

    results = await find_issues(
        github_client,
        language="python",
        max_results=999,
        enable_scoring=False,
        unassigned_only=False,
    )

    # `clamp_max_results` caps to 25, only 5 issues exist → all returned.
    assert len(results) == 5


@pytest.mark.asyncio
async def test_find_issues_normalises_language(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    route = _mock_repo_search(respx_mock, [])

    await find_issues(
        github_client,
        language="  Python  ",
        enable_scoring=False,
    )

    q = route.calls.last.request.url.params.get("q") or ""
    assert "language:python" in q


@pytest.mark.asyncio
async def test_find_issues_passes_labels_to_per_repo_endpoint(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    _mock_repo_search(
        respx_mock,
        [{"full_name": "acme/widgets", "stargazers_count": 1000, "topics": []}],
    )
    issues_route = _mock_repo_issues(respx_mock, "acme/widgets", [])

    await find_issues(
        github_client,
        language="python",
        labels=["good first issue", "help wanted"],
        enable_scoring=False,
    )

    params = issues_route.calls.last.request.url.params
    assert params.get("labels") == "good first issue,help wanted"
    assert params.get("state") == "open"


@pytest.mark.asyncio
async def test_find_issues_skips_pull_requests(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    _mock_repo_search(
        respx_mock,
        [{"full_name": "acme/widgets", "stargazers_count": 1000, "topics": []}],
    )
    issue = _issue(title="Real issue", repo="acme/widgets", number=1)
    pr = _issue(title="PR not issue", repo="acme/widgets", number=2)
    pr["pull_request"] = {"url": "https://api.github.com/repos/acme/widgets/pulls/2"}
    _mock_repo_issues(respx_mock, "acme/widgets", [pr, issue])

    results = await find_issues(
        github_client,
        language="python",
        enable_scoring=False,
        unassigned_only=False,
    )

    assert [r.title for r in results] == ["Real issue"]


@pytest.mark.asyncio
async def test_find_issues_empty_repo_search_returns_empty(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    _mock_repo_search(respx_mock, [])

    results = await find_issues(
        github_client,
        language="python",
        enable_scoring=False,
    )

    assert results == []


@pytest.mark.asyncio
async def test_find_issues_rejects_injection_in_label(
    github_client: GitHubClient,
) -> None:
    from gfi_scout.utils.validators import ValidationError

    with pytest.raises(ValidationError):
        await find_issues(
            github_client,
            language="python",
            labels=['good first issue" stars:0..0 "'],
            enable_scoring=False,
        )


@pytest.mark.asyncio
async def test_find_issues_rejects_injection_in_topic(
    github_client: GitHubClient,
) -> None:
    from gfi_scout.utils.validators import ValidationError

    with pytest.raises(ValidationError):
        await find_issues(
            github_client,
            language="python",
            topic="web stars:0..0",
            enable_scoring=False,
        )


@pytest.mark.asyncio
async def test_find_issues_truncates_body_preview(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    long_body = "x" * (BODY_PREVIEW_CHARS + 200)
    _mock_repo_search(
        respx_mock,
        [{"full_name": "acme/widgets", "stargazers_count": 1000, "topics": []}],
    )
    _mock_repo_issues(
        respx_mock,
        "acme/widgets",
        [_issue(title="long", repo="acme/widgets", number=1, body=long_body)],
    )

    results = await find_issues(
        github_client,
        language="python",
        enable_scoring=False,
        unassigned_only=False,
    )

    assert results[0].body_preview.endswith("…")
    assert len(results[0].body_preview) <= BODY_PREVIEW_CHARS + 1
