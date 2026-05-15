from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from gfi_scout.services.github_api import GitHubClient
from gfi_scout.tools.find_issues import (
    BODY_PREVIEW_CHARS,
    build_search_query,
    find_issues,
)


class TestBuildSearchQuery:
    def test_includes_label_language_stars_state(self) -> None:
        query = build_search_query(
            language="python",
            labels=["good first issue"],
            min_stars=50,
            max_stars=50000,
            topic=None,
        )
        assert 'label:"good first issue"' in query
        assert "language:python" in query
        assert "stars:50..50000" in query
        assert "state:open" in query
        assert "is:issue" in query
        assert "no:assignee" in query

    def test_appends_topic_when_given(self) -> None:
        query = build_search_query(
            language="python",
            labels=["good first issue"],
            min_stars=50,
            max_stars=50000,
            topic="cli",
        )
        assert "topic:cli" in query

    def test_supports_multiple_labels(self) -> None:
        query = build_search_query(
            language="rust",
            labels=["good first issue", "help wanted"],
            min_stars=10,
            max_stars=1000,
            topic=None,
        )
        assert 'label:"good first issue"' in query
        assert 'label:"help wanted"' in query

    def test_unassigned_only_false_drops_no_assignee(self) -> None:
        query = build_search_query(
            language="python",
            labels=["good first issue"],
            min_stars=50,
            max_stars=50000,
            topic=None,
            unassigned_only=False,
        )
        assert "no:assignee" not in query

    def test_clamps_negative_and_inverted_star_bounds(self) -> None:
        query = build_search_query(
            language="python",
            labels=["good first issue"],
            min_stars=-100,
            max_stars=-5,
            topic=None,
        )
        # Negative bounds coerced to 0..0; never produces a malformed range.
        assert "stars:0..0" in query


@pytest.mark.asyncio
async def test_find_issues_maps_response_to_issue_results(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    github_client: GitHubClient,
) -> None:
    respx_mock.get("/search/issues").mock(return_value=httpx.Response(200, json=sample_issues))

    results = await find_issues(
        github_client,
        language="python",
        max_results=10,
        enable_scoring=False,
    )

    assert len(results) == 2
    first = results[0]
    assert first.title == "Add type hints to utils module"
    assert str(first.url) == "https://github.com/acme/widgets/issues/42"
    assert first.repo_full_name == "acme/widgets"
    assert "good first issue" in first.labels
    assert first.is_assigned is False

    second = results[1]
    assert second.is_assigned is True


@pytest.mark.asyncio
async def test_find_issues_clamps_max_results(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    github_client: GitHubClient,
) -> None:
    route = respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(200, json=sample_issues)
    )

    await find_issues(
        github_client,
        language="python",
        max_results=999,
        enable_scoring=False,
    )

    request = route.calls.last.request
    assert request.url.params.get("per_page") == "25"


@pytest.mark.asyncio
async def test_find_issues_normalises_language(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    github_client: GitHubClient,
) -> None:
    route = respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(200, json=sample_issues)
    )

    await find_issues(
        github_client,
        language="  Python  ",
        enable_scoring=False,
    )

    request = route.calls.last.request
    q = request.url.params.get("q") or ""
    assert "language:python" in q


@pytest.mark.asyncio
async def test_find_issues_unassigned_only_false_passed_to_query(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    github_client: GitHubClient,
) -> None:
    route = respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(200, json=sample_issues)
    )

    await find_issues(
        github_client,
        language="python",
        enable_scoring=False,
        unassigned_only=False,
    )

    q = route.calls.last.request.url.params.get("q") or ""
    assert "no:assignee" not in q


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
    payload = {
        "total_count": 1,
        "incomplete_results": False,
        "items": [
            {
                "title": "long",
                "html_url": "https://github.com/a/b/issues/1",
                "body": long_body,
                "repository_url": "https://api.github.com/repos/a/b",
                "labels": [],
                "assignee": None,
                "assignees": [],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ],
    }
    respx_mock.get("/search/issues").mock(return_value=httpx.Response(200, json=payload))

    results = await find_issues(
        github_client,
        language="python",
        enable_scoring=False,
    )

    assert results[0].body_preview.endswith("…")
    assert len(results[0].body_preview) <= BODY_PREVIEW_CHARS + 1
