"""Shared test fixtures.

Two safety layers prevent any test from making a real network call:

1. `assert_all_mocked=True` on the `respx_mock` fixture — any HTTP request that
   doesn't match a registered route raises `respx.MockError`.
2. The autouse `_block_real_http` fixture monkeypatches `httpx.AsyncClient.send`
   and refuses any request to `api.github.com` unless the `respx_mock` fixture
   is currently active for this test. Belt-and-suspenders against tests that
   forget to use the `respx_mock` fixture.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
import respx

from gfi_scout.services.github_api import GITHUB_API_BASE, GitHubClient

FIXTURES = Path(__file__).parent / "fixtures"

_respx_active: bool = False


@pytest.fixture
def sample_issues() -> dict[str, Any]:
    with (FIXTURES / "sample_issues.json").open(encoding="utf-8") as fp:
        return json.load(fp)


@pytest.fixture
def respx_mock() -> Iterator[respx.MockRouter]:
    """Mock router pinned to api.github.com. Any unrouted call raises."""
    global _respx_active
    with respx.mock(
        base_url=GITHUB_API_BASE,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as router:
        _respx_active = True
        try:
            yield router
        finally:
            _respx_active = False


@pytest_asyncio.fixture
async def github_client() -> AsyncIterator[GitHubClient]:
    client = GitHubClient(token="test-token")
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture(autouse=True)
def _block_real_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Belt-and-suspenders guard: forbid real outbound HTTP to api.github.com.

    Any test that hits api.github.com without first activating the `respx_mock`
    fixture raises immediately, so a missing mock can never silently leak to
    the real GitHub API.
    """
    original_send = httpx.AsyncClient.send

    async def guarded_send(
        self: httpx.AsyncClient,
        request: httpx.Request,
        **kwargs: Any,
    ) -> httpx.Response:
        host = request.url.host or ""
        if host.endswith("api.github.com") and not _respx_active:
            raise RuntimeError(f"real HTTP call escaped test mock: {request.method} {request.url}")
        return await original_send(self, request, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", guarded_send)
