"""Async GitLab REST API client (Phase 3).

GFI Scout treats GitLab as a secondary source. We expose the bare minimum to
make `find_issues` work cross-platform: project lookup + issue listing
filtered by labels.

Endpoint reference: https://docs.gitlab.com/ee/api/
"""

from __future__ import annotations

import time
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx

from gfi_scout.utils.logger import get_logger

GITLAB_API_BASE = "https://gitlab.com/api/v4"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_PER_PAGE = 100

log = get_logger(__name__)


class GitLabAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str, *, url: str) -> None:
        super().__init__(f"GitLab API error {status_code} on {url}: {message}")
        self.status_code = status_code
        self.url = url


class GitLabClient:
    """Thin async GitLab client.

    Auth is optional — public projects work anonymously but rate limits are
    tight, so we pass a PAT in production.
    """

    def __init__(
        self,
        *,
        token: str | None = None,
        base_url: str = GITLAB_API_BASE,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        headers = {
            "Accept": "application/json",
            "User-Agent": "gfi-scout/0.1.0",
        }
        if token:
            headers["PRIVATE-TOKEN"] = token
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

    async def _get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        start = time.perf_counter()
        try:
            response = await self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            log.exception("GitLab request failed: %s", exc)
            raise GitLabAPIError(0, str(exc), url=url) from exc
        duration_ms = (time.perf_counter() - start) * 1000
        log.info(
            "gitlab_api request=%s status=%s duration_ms=%.1f params=%s",
            url,
            response.status_code,
            duration_ms,
            params,
        )
        if response.status_code >= 400:
            raise GitLabAPIError(
                response.status_code,
                response.text[:500],
                url=url,
            )
        data: list[dict[str, Any]] | dict[str, Any] = response.json()
        return data

    async def search_issues(
        self,
        *,
        labels: list[str],
        language: str | None = None,
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """Search public issues with the given labels across all of GitLab.

        Language filtering on GitLab requires per-project lookup (no global
        language field on the issues endpoint), so we surface raw issues and
        let the caller filter by project metadata if needed.
        """
        if per_page > MAX_PER_PAGE:
            per_page = MAX_PER_PAGE
        if page < 1:
            page = 1
        params: dict[str, Any] = {
            "labels": ",".join(labels),
            "scope": "all",
            "state": "opened",
            "per_page": per_page,
            "page": page,
        }
        if language:
            params["search"] = language
        data = await self._get("/issues", params=params)
        return list(data) if isinstance(data, list) else []

    async def get_project(self, project_path: str) -> dict[str, Any]:
        encoded = quote(project_path, safe="")
        data = await self._get(f"/projects/{encoded}")
        if not isinstance(data, dict):
            raise GitLabAPIError(
                500,
                "unexpected response shape",
                url=f"/projects/{encoded}",
            )
        return data
