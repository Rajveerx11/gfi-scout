"""Shared runtime wiring for MCP, CLI, and TUI entry points."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Self

from gfi_scout.config import CacheBackend, Settings, load_settings
from gfi_scout.services.cache import SQLiteCache, TTLNamespaceCache
from gfi_scout.services.github_api import GitHubClient

ConfigurableCache = TTLNamespaceCache | SQLiteCache
_SQLITE_RUNTIME_CACHES: dict[tuple[int, str], SQLiteCache] = {}


def _credential_partition(token: str | None) -> str:
    if token is None:
        return "anonymous"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_cache(
    settings_ttl_minutes: int,
    *,
    backend: CacheBackend = "memory",
    sqlite_path: Path | None = None,
    credential_partition: str = "anonymous",
) -> ConfigurableCache:
    """Build a namespaced TTL cache with sensible per-namespace defaults."""
    cache: ConfigurableCache
    if backend == "sqlite":
        cache = SQLiteCache(
            sqlite_path,
            partition=credential_partition,
            default_ttl_seconds=settings_ttl_minutes * 60,
        )
    else:
        cache = TTLNamespaceCache(default_ttl_seconds=settings_ttl_minutes * 60)
    cache.configure_namespace("search_issues", ttl_seconds=600)
    cache.configure_namespace("search_repositories", ttl_seconds=1800)
    cache.configure_namespace("repo", ttl_seconds=settings_ttl_minutes * 60)
    cache.configure_namespace("repo_issues", ttl_seconds=300)
    cache.configure_namespace("repo_pulls", ttl_seconds=settings_ttl_minutes * 60)
    cache.configure_namespace("repo_contributors", ttl_seconds=settings_ttl_minutes * 60)
    cache.configure_namespace("issue", ttl_seconds=300)
    cache.configure_namespace("issue_comments", ttl_seconds=300)
    cache.configure_namespace("issue_timeline", ttl_seconds=300)
    cache.configure_namespace("repo_content", ttl_seconds=3600)
    return cache


def _runtime_cache(settings: Settings) -> ConfigurableCache:
    partition = _credential_partition(settings.github_token)
    if settings.cache_backend == "memory":
        return build_cache(settings.cache_ttl_minutes)

    key = (settings.cache_ttl_minutes, partition)
    cache = _SQLITE_RUNTIME_CACHES.get(key)
    if cache is None:
        built = build_cache(
            settings.cache_ttl_minutes,
            backend="sqlite",
            credential_partition=partition,
        )
        assert isinstance(built, SQLiteCache)
        cache = built
        _SQLITE_RUNTIME_CACHES[key] = cache
    return cache


class _RuntimeGitHubClient(GitHubClient):
    def __init__(self, token: str | None, cache: ConfigurableCache) -> None:
        self._startup_cache = cache
        super().__init__(token=token, cache=cache)

    async def __aenter__(self) -> Self:
        if isinstance(self._startup_cache, SQLiteCache):
            await self._startup_cache.wait_ready()
        return self


def make_client(settings: Settings | None = None) -> GitHubClient:
    """Create a GitHub API client from loaded settings."""
    effective_settings = settings or load_settings()
    return _RuntimeGitHubClient(
        effective_settings.github_token,
        _runtime_cache(effective_settings),
    )
