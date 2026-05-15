from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from gfi_scout.services.github_api import (
    GITHUB_API_BASE,
    GITHUB_API_VERSION,
    GitHubAPIError,
    GitHubClient,
)


@pytest.mark.asyncio
async def test_search_issues_sends_auth_and_version_headers(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    github_client: GitHubClient,
) -> None:
    route = respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(200, json=sample_issues)
    )

    await github_client.search_issues("language:python", per_page=10, page=1)

    assert route.called
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer test-token"
    assert request.headers["accept"] == "application/vnd.github+json"
    assert request.headers["x-github-api-version"] == GITHUB_API_VERSION
    assert request.url.params.get("q") == "language:python"
    assert request.url.params.get("per_page") == "10"
    assert request.url.params.get("page") == "1"


@pytest.mark.asyncio
async def test_search_issues_returns_typed_response(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    github_client: GitHubClient,
) -> None:
    respx_mock.get("/search/issues").mock(return_value=httpx.Response(200, json=sample_issues))

    result = await github_client.search_issues("language:python")

    assert result.total_count == 2
    assert result.incomplete_results is False
    assert len(result.items) == 2
    assert result.items[0].title == "Add type hints to utils module"


@pytest.mark.asyncio
async def test_search_issues_clamps_per_page(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    github_client: GitHubClient,
) -> None:
    route = respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(200, json=sample_issues)
    )

    await github_client.search_issues("q", per_page=500, page=0)

    request = route.calls.last.request
    assert request.url.params.get("per_page") == "100"
    assert request.url.params.get("page") == "1"


@pytest.mark.asyncio
async def test_search_issues_raises_on_4xx(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(422, json={"message": "Validation Failed"})
    )

    with pytest.raises(GitHubAPIError) as exc_info:
        await github_client.search_issues("bad query")

    assert exc_info.value.status_code == 422


def test_constructor_requires_token() -> None:
    with pytest.raises(ValueError, match="token"):
        GitHubClient(token="")


def test_base_url_default() -> None:
    assert GITHUB_API_BASE == "https://api.github.com"
