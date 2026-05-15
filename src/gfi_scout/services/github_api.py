"""Async GitHub REST API client.

Phase 2+: search issues, fetch repos, PRs, contributors, issue comments,
issue timeline, repository content (CONTRIBUTING.md). All async, all wrapped
in `GitHubAPIError` on non-2xx responses. Optional `Cache` injected for
namespace-scoped TTL caching.
"""

from __future__ import annotations

import base64
import time
from types import TracebackType
from typing import Any, Self

import httpx

from gfi_scout.models.issue import GitHubIssueRaw, SearchIssuesResponse
from gfi_scout.models.repo import RepoSummary
from gfi_scout.services.cache import Cache, NullCache
from gfi_scout.utils.logger import get_logger

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_PER_PAGE = 100

NS_SEARCH = "search_issues"
NS_REPO = "repo"
NS_PRS = "repo_pulls"
NS_CONTRIB = "repo_contributors"
NS_ISSUE = "issue"
NS_ISSUE_COMMENTS = "issue_comments"
NS_ISSUE_TIMELINE = "issue_timeline"
NS_CONTENT = "repo_content"

log = get_logger(__name__)


class GitHubAPIError(RuntimeError):
    """Raised on any non-2xx response from the GitHub API."""

    def __init__(self, status_code: int, message: str, *, url: str) -> None:
        super().__init__(f"GitHub API error {status_code} on {url}: {message}")
        self.status_code = status_code
        self.url = url


class GitHubNotFoundError(GitHubAPIError):
    """Raised on 404 — used by callers that probe optional resources."""


class GitHubClient:
    """Async GitHub client with optional namespace cache."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = GITHUB_API_BASE,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.AsyncClient | None = None,
        cache: Cache | None = None,
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
        self._cache: Cache = cache if cache is not None else NullCache()

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

    # ---- internals --------------------------------------------------------

    def _cache_get(self, namespace: str, *parts: object) -> object | None:
        return self._cache.get(namespace, *parts)

    def _cache_set(self, namespace: str, *parts: object, value: object) -> None:
        self._cache.set(namespace, *parts, value=value)

    async def _get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> Any | None:
        start = time.perf_counter()
        try:
            response = await self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            log.exception("GitHub request failed: %s", exc)
            raise GitHubAPIError(0, str(exc), url=url) from exc

        duration_ms = (time.perf_counter() - start) * 1000
        log.info(
            "github_api request=%s status=%s duration_ms=%.1f params=%s",
            url,
            response.status_code,
            duration_ms,
            params,
        )

        if response.status_code == 404 and allow_404:
            return None
        if response.status_code == 404:
            raise GitHubNotFoundError(404, response.text[:300], url=url)
        if response.status_code >= 400:
            raise GitHubAPIError(
                response.status_code,
                response.text[:500],
                url=url,
            )
        if not response.content:
            return None
        return response.json()

    # ---- search ----------------------------------------------------------

    async def search_issues(
        self,
        query: str,
        *,
        per_page: int = 30,
        page: int = 1,
    ) -> SearchIssuesResponse:
        if per_page < 1:
            per_page = 1
        if per_page > MAX_PER_PAGE:
            per_page = MAX_PER_PAGE
        if page < 1:
            page = 1
        cache_key = (query, per_page, page)
        cached = self._cache_get(NS_SEARCH, *cache_key)
        if isinstance(cached, SearchIssuesResponse):
            return cached
        params: dict[str, Any] = {
            "q": query,
            "per_page": per_page,
            "page": page,
        }
        data = await self._get_json("/search/issues", params=params)
        parsed = SearchIssuesResponse.model_validate(data)
        self._cache_set(NS_SEARCH, *cache_key, value=parsed)
        return parsed

    # ---- repositories ----------------------------------------------------

    async def get_repo(self, repo_full_name: str) -> RepoSummary:
        cached = self._cache_get(NS_REPO, repo_full_name)
        if isinstance(cached, RepoSummary):
            return cached
        data = await self._get_json(f"/repos/{repo_full_name}")
        assert isinstance(data, dict)
        summary = RepoSummary(
            full_name=data.get("full_name", repo_full_name),
            stars=data.get("stargazers_count"),
            language=data.get("language"),
            default_branch=data.get("default_branch"),
            pushed_at=data.get("pushed_at"),
            open_issues_count=data.get("open_issues_count"),
            topics=list(data.get("topics") or []),
        )
        self._cache_set(NS_REPO, repo_full_name, value=summary)
        return summary

    async def list_pulls(
        self,
        repo_full_name: str,
        *,
        state: str = "closed",
        per_page: int = 50,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        if per_page > MAX_PER_PAGE:
            per_page = MAX_PER_PAGE
        cache_key = (repo_full_name, state, per_page, page)
        cached = self._cache_get(NS_PRS, *cache_key)
        if isinstance(cached, list):
            return cached
        data = await self._get_json(
            f"/repos/{repo_full_name}/pulls",
            params={
                "state": state,
                "per_page": per_page,
                "page": page,
                "sort": "updated",
                "direction": "desc",
            },
        )
        result = list(data) if isinstance(data, list) else []
        self._cache_set(NS_PRS, *cache_key, value=result)
        return result

    async def list_contributors(
        self,
        repo_full_name: str,
        *,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        if per_page > MAX_PER_PAGE:
            per_page = MAX_PER_PAGE
        cache_key = (repo_full_name, per_page)
        cached = self._cache_get(NS_CONTRIB, *cache_key)
        if isinstance(cached, list):
            return cached
        data = await self._get_json(
            f"/repos/{repo_full_name}/contributors",
            params={"per_page": per_page, "anon": "false"},
            allow_404=True,
        )
        result = list(data) if isinstance(data, list) else []
        self._cache_set(NS_CONTRIB, *cache_key, value=result)
        return result

    async def list_commits(
        self,
        repo_full_name: str,
        *,
        since_iso: str | None = None,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        if per_page > MAX_PER_PAGE:
            per_page = MAX_PER_PAGE
        params: dict[str, Any] = {"per_page": per_page}
        if since_iso:
            params["since"] = since_iso
        data = await self._get_json(
            f"/repos/{repo_full_name}/commits",
            params=params,
            allow_404=True,
        )
        return list(data) if isinstance(data, list) else []

    # ---- issue detail -----------------------------------------------------

    async def get_issue(
        self,
        repo_full_name: str,
        number: int,
    ) -> GitHubIssueRaw:
        cache_key = (repo_full_name, number)
        cached = self._cache_get(NS_ISSUE, *cache_key)
        if isinstance(cached, GitHubIssueRaw):
            return cached
        data = await self._get_json(f"/repos/{repo_full_name}/issues/{number}")
        assert isinstance(data, dict)
        # Issues endpoint returns repository_url derived from the issue URL.
        if "repository_url" not in data:
            data["repository_url"] = f"{GITHUB_API_BASE}/repos/{repo_full_name}"
        parsed = GitHubIssueRaw.model_validate(data)
        self._cache_set(NS_ISSUE, *cache_key, value=parsed)
        return parsed

    async def list_issue_comments(
        self,
        repo_full_name: str,
        number: int,
        *,
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        if per_page > MAX_PER_PAGE:
            per_page = MAX_PER_PAGE
        cache_key = (repo_full_name, number, per_page)
        cached = self._cache_get(NS_ISSUE_COMMENTS, *cache_key)
        if isinstance(cached, list):
            return cached
        data = await self._get_json(
            f"/repos/{repo_full_name}/issues/{number}/comments",
            params={"per_page": per_page},
            allow_404=True,
        )
        result = list(data) if isinstance(data, list) else []
        self._cache_set(NS_ISSUE_COMMENTS, *cache_key, value=result)
        return result

    async def list_issue_timeline(
        self,
        repo_full_name: str,
        number: int,
        *,
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        if per_page > MAX_PER_PAGE:
            per_page = MAX_PER_PAGE
        cache_key = (repo_full_name, number, per_page)
        cached = self._cache_get(NS_ISSUE_TIMELINE, *cache_key)
        if isinstance(cached, list):
            return cached
        data = await self._get_json(
            f"/repos/{repo_full_name}/issues/{number}/timeline",
            params={"per_page": per_page},
            allow_404=True,
        )
        result = list(data) if isinstance(data, list) else []
        self._cache_set(NS_ISSUE_TIMELINE, *cache_key, value=result)
        return result

    # ---- file content ----------------------------------------------------

    async def get_content_text(
        self,
        repo_full_name: str,
        path: str,
        *,
        ref: str | None = None,
    ) -> str | None:
        """Fetch a file's text via the Contents API. None on 404."""
        cache_key = (repo_full_name, path, ref or "")
        cached = self._cache_get(NS_CONTENT, *cache_key)
        if isinstance(cached, str):
            return cached
        params: dict[str, Any] = {}
        if ref:
            params["ref"] = ref
        data = await self._get_json(
            f"/repos/{repo_full_name}/contents/{path}",
            params=params or None,
            allow_404=True,
        )
        if data is None:
            self._cache_set(NS_CONTENT, *cache_key, value=None)
            return None
        if isinstance(data, list):
            return None
        encoded = data.get("content") if isinstance(data, dict) else None
        if not isinstance(encoded, str):
            return None
        try:
            text = base64.b64decode(encoded).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            return None
        self._cache_set(NS_CONTENT, *cache_key, value=text)
        return text

    async def path_exists(
        self,
        repo_full_name: str,
        path: str,
    ) -> bool:
        """True if `path` exists at repo root (or as a directory)."""
        data = await self._get_json(
            f"/repos/{repo_full_name}/contents/{path}",
            allow_404=True,
        )
        return data is not None
