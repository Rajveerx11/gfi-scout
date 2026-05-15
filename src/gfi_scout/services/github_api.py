"""Async GitHub REST API client (search-only in Phase 1)."""

from __future__ import annotations

import time
from types import TracebackType
from typing import Self

import httpx

from gfi_scout.models.issue import SearchIssuesResponse
from gfi_scout.utils.logger import get_logger

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_PER_PAGE = 100

log = get_logger(__name__)


class GitHubAPIError(RuntimeError):
    """Raised on any non-2xx response from the GitHub API."""

    def __init__(self, status_code: int, message: str, *, url: str) -> None:
        super().__init__(f"GitHub API error {status_code} on {url}: {message}")
        self.status_code = status_code
        self.url = url


class GitHubClient:
    """Thin async wrapper around `GET /search/issues` for Phase 1."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = GITHUB_API_BASE,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not token:
            raise ValueError("GitHub token is required")
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "gfi-scout/0.1.0",
        }
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search_issues(
        self,
        query: str,
        *,
        per_page: int = 30,
        page: int = 1,
    ) -> SearchIssuesResponse:
        """Call `GET /search/issues`.

        Args:
            query: Raw GitHub search qualifier string, e.g.
                `label:"good first issue" language:python state:open`.
            per_page: Page size, clamped to GitHub's 100 max.
            page: 1-indexed page number.
        """
        if per_page < 1:
            per_page = 1
        if per_page > MAX_PER_PAGE:
            per_page = MAX_PER_PAGE
        if page < 1:
            page = 1

        params: dict[str, str | int] = {
            "q": query,
            "per_page": per_page,
            "page": page,
        }
        url = "/search/issues"
        start = time.perf_counter()
        try:
            response = await self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            log.exception("GitHub request failed: %s", exc)
            raise GitHubAPIError(0, str(exc), url=url) from exc

        duration_ms = (time.perf_counter() - start) * 1000
        log.info(
            "github_api request=%s status=%s duration_ms=%.1f q=%r",
            url,
            response.status_code,
            duration_ms,
            query,
        )

        if response.status_code >= 400:
            raise GitHubAPIError(
                response.status_code,
                response.text[:500],
                url=url,
            )

        return SearchIssuesResponse.model_validate(response.json())
