from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

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
async def test_search_repositories_returns_repo_summaries(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    route = respx_mock.get("/search/repositories").mock(
        return_value=httpx.Response(
            200,
            json={
                "total_count": 1,
                "incomplete_results": False,
                "items": [
                    {
                        "full_name": "acme/widgets",
                        "stargazers_count": 1200,
                        "language": "Python",
                        "default_branch": "main",
                        "open_issues_count": 12,
                        "topics": ["cli"],
                    }
                ],
            },
        )
    )

    result = await github_client.search_repositories(
        "language:python stars:50..50000",
        per_page=500,
        page=0,
    )

    assert len(result) == 1
    assert result[0].full_name == "acme/widgets"
    assert result[0].stars == 1200
    assert result[0].language == "Python"
    assert result[0].topics == ["cli"]
    request = route.calls.last.request
    assert request.url.params.get("q") == "language:python stars:50..50000"
    assert request.url.params.get("sort") == "stars"
    assert request.url.params.get("order") == "desc"
    assert request.url.params.get("per_page") == "100"
    assert request.url.params.get("page") == "1"


@pytest.mark.asyncio
async def test_list_repo_issues_filters_prs_and_synthesizes_repo_url(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    route = respx_mock.get("/repos/acme/widgets/issues").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "title": "Real issue",
                    "html_url": "https://github.com/acme/widgets/issues/1",
                    "body": "starter task",
                    "labels": [{"name": "good first issue"}],
                    "assignee": None,
                    "assignees": [],
                    "created_at": "2026-04-01T12:00:00Z",
                    "updated_at": "2026-05-10T09:30:00Z",
                },
                {
                    "title": "Pull request",
                    "html_url": "https://github.com/acme/widgets/pull/2",
                    "pull_request": {"url": "https://api.github.com/repos/acme/widgets/pulls/2"},
                    "labels": [],
                    "assignee": None,
                    "assignees": [],
                    "created_at": "2026-04-01T12:00:00Z",
                    "updated_at": "2026-05-10T09:30:00Z",
                },
            ],
        )
    )

    result = await github_client.list_repo_issues(
        "acme/widgets",
        labels=["good first issue", "help wanted"],
        per_page=500,
        page=0,
    )

    assert len(result) == 1
    assert result[0].title == "Real issue"
    assert str(result[0].repository_url) == "https://api.github.com/repos/acme/widgets"
    request = route.calls.last.request
    assert request.url.params.get("labels") == "good first issue,help wanted"
    assert request.url.params.get("per_page") == "100"
    assert request.url.params.get("page") == "1"


@pytest.mark.asyncio
async def test_search_issues_raises_on_4xx(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    route = respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(422, json={"message": "Validation Failed"})
    )

    with pytest.raises(GitHubAPIError) as exc_info:
        await github_client.search_issues("bad query")

    assert exc_info.value.status_code == 422
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_rate_limit_retries_once_then_succeeds(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    github_client: GitHubClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    route = respx_mock.get("/search/issues").mock(
        side_effect=[
            httpx.Response(
                429,
                headers={"Retry-After": "2"},
                json={"message": "Too many requests"},
            ),
            httpx.Response(200, json=sample_issues),
        ]
    )
    sleep = AsyncMock()
    monkeypatch.setattr("gfi_scout.services.github_api.asyncio.sleep", sleep)

    import logging

    with caplog.at_level(logging.WARNING, logger="gfi_scout.services.github_api"):
        result = await github_client.search_issues("q")

    assert result.total_count == 2
    assert route.call_count == 2
    sleep.assert_awaited_once_with(2.0)
    assert "github_api retry" in caplog.text
    assert "status=429" in caplog.text


@pytest.mark.asyncio
async def test_rate_limit_gives_up_after_one_retry(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(
            403,
            headers={"Retry-After": "0", "X-RateLimit-Reset": "1700000000"},
            json={"message": "API rate limit exceeded"},
        )
    )
    sleep = AsyncMock()
    monkeypatch.setattr("gfi_scout.services.github_api.asyncio.sleep", sleep)

    with pytest.raises(GitHubAPIError) as exc_info:
        await github_client.search_issues("q")

    assert exc_info.value.status_code == 403
    assert route.call_count == 2
    sleep.assert_awaited_once_with(0.0)
    assert "rate limit exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_secondary_rate_limit_retries_with_fallback_delay(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    github_client: GitHubClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = respx_mock.get("/search/issues").mock(
        side_effect=[
            httpx.Response(
                403,
                json={"message": "You have exceeded a secondary rate limit."},
            ),
            httpx.Response(200, json=sample_issues),
        ]
    )
    sleep = AsyncMock()
    monkeypatch.setattr("gfi_scout.services.github_api.asyncio.sleep", sleep)

    result = await github_client.search_issues("q")

    assert result.total_count == 2
    assert route.call_count == 2
    sleep.assert_awaited_once_with(1.0)


@pytest.mark.asyncio
async def test_concurrent_rate_limit_retries_are_staggered(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    github_client: GitHubClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: dict[str, int] = {}
    both_rate_limited = asyncio.Event()

    async def respond(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        attempts[query] = attempts.get(query, 0) + 1
        if attempts[query] == 1:
            if len(attempts) == 2:
                both_rate_limited.set()
            await both_rate_limited.wait()
            return httpx.Response(
                429,
                headers={"Retry-After": "1"},
                json={"message": "Too many requests"},
            )
        return httpx.Response(200, json=sample_issues)

    route = respx_mock.get("/search/issues").mock(side_effect=respond)
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("gfi_scout.services.github_api.asyncio.sleep", record_sleep)
    monkeypatch.setattr("gfi_scout.services.github_api.time.monotonic", lambda: 100.0)

    results = await asyncio.gather(
        github_client.search_issues("first"),
        github_client.search_issues("second"),
    )

    assert [result.total_count for result in results] == [2, 2]
    assert route.call_count == 4
    assert delays == pytest.approx([1.0, 1.1])


@pytest.mark.asyncio
async def test_concurrent_retry_schedule_stays_within_delay_cap(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    github_client: GitHubClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: dict[str, int] = {}
    all_rate_limited = asyncio.Event()

    async def respond(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        attempts[query] = attempts.get(query, 0) + 1
        if attempts[query] == 1:
            if len(attempts) == 3:
                all_rate_limited.set()
            await all_rate_limited.wait()
            return httpx.Response(
                429,
                headers={"Retry-After": "9.9"},
                json={"message": "Too many requests"},
            )
        return httpx.Response(200, json=sample_issues)

    route = respx_mock.get("/search/issues").mock(side_effect=respond)
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("gfi_scout.services.github_api.asyncio.sleep", record_sleep)
    monkeypatch.setattr("gfi_scout.services.github_api.time.monotonic", lambda: 100.0)

    results = await asyncio.gather(
        github_client.search_issues("first"),
        github_client.search_issues("second"),
        github_client.search_issues("third"),
        return_exceptions=True,
    )

    assert sum(isinstance(result, GitHubAPIError) for result in results) == 1
    assert route.call_count == 5
    assert delays == pytest.approx([9.9, 10.0])
    assert max(delays) <= 10.0


@pytest.mark.asyncio
async def test_long_retry_after_gives_up_without_retry(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    route = respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(
            429,
            headers={"Retry-After": "60"},
            json={"message": "Too many requests"},
        )
    )

    with pytest.raises(GitHubAPIError) as exc_info:
        await github_client.search_issues("q")

    assert exc_info.value.status_code == 429
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_tokenless_client_omits_auth_header(
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
) -> None:
    route = respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(200, json=sample_issues)
    )

    async with GitHubClient(token=None) as client:
        await client.search_issues("language:python")

    assert "authorization" not in route.calls.last.request.headers


@pytest.mark.asyncio
async def test_403_tokenless_hints_to_set_token(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
            json={"message": "API rate limit exceeded"},
        )
    )

    async with GitHubClient(token=None) as client:
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.search_issues("q")

    assert "60/hour" in str(exc_info.value)
    assert "GITHUB_TOKEN" in str(exc_info.value)


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
    respx_mock.get("/search/issues").mock(side_effect=httpx.ConnectError("dns failure"))

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
