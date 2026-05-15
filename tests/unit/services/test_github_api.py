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


@pytest.mark.asyncio
async def test_401_returns_helpful_token_message(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )

    with pytest.raises(GitHubAPIError) as exc_info:
        await github_client.search_issues("q")

    assert exc_info.value.status_code == 401
    assert "GITHUB_TOKEN" in str(exc_info.value)
    assert "invalid or expired" in str(exc_info.value)


@pytest.mark.asyncio
async def test_403_returns_rate_limit_message_with_reset(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
            json={"message": "API rate limit exceeded"},
        )
    )

    with pytest.raises(GitHubAPIError) as exc_info:
        await github_client.search_issues("q")

    assert exc_info.value.status_code == 403
    msg = str(exc_info.value)
    assert "rate limit exceeded" in msg
    assert "2023-11-14" in msg  # 1700000000 → 2023-11-14T22:13:20+00:00


@pytest.mark.asyncio
async def test_403_without_reset_header_renders_unknown_time(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )

    with pytest.raises(GitHubAPIError) as exc_info:
        await github_client.search_issues("q")

    assert "unknown time" in str(exc_info.value)


@pytest.mark.asyncio
async def test_404_returns_not_found_message(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    respx_mock.get("/repos/owner/missing").mock(return_value=httpx.Response(404))

    with pytest.raises(GitHubAPIError) as exc_info:
        await github_client.get_repo("owner/missing")

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_network_error_returns_connection_message(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    respx_mock.get("/search/issues").mock(
        side_effect=httpx.ConnectError("dns failure")
    )

    with pytest.raises(GitHubAPIError) as exc_info:
        await github_client.search_issues("q")

    assert exc_info.value.status_code == 0
    assert "Could not connect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_logs_rate_limit_headers(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    github_client: GitHubClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(
            200,
            headers={"X-RateLimit-Remaining": "4999", "X-RateLimit-Reset": "1700000000"},
            json=sample_issues,
        )
    )

    import logging

    with caplog.at_level(logging.INFO, logger="gfi_scout.services.github_api"):
        await github_client.search_issues("q")

    record = next(r for r in caplog.records if "github_api method=GET" in r.getMessage())
    msg = record.getMessage()
    assert "rate_remaining=4999" in msg
    assert "rate_reset=1700000000" in msg
    assert "duration_ms=" in msg
