"""Shared runtime wiring for MCP, CLI, and TUI entry points."""

from __future__ import annotations

from gfi_scout.config import Settings, load_settings
from gfi_scout.services.cache import TTLNamespaceCache
from gfi_scout.services.github_api import GitHubClient


def build_cache(settings_ttl_minutes: int) -> TTLNamespaceCache:
    """Build a namespaced TTL cache with sensible per-namespace defaults."""
    cache = TTLNamespaceCache(default_ttl_seconds=settings_ttl_minutes * 60)
    cache.configure_namespace("search_issues", ttl_seconds=600)
    cache.configure_namespace("repo", ttl_seconds=settings_ttl_minutes * 60)
    cache.configure_namespace("repo_pulls", ttl_seconds=settings_ttl_minutes * 60)
    cache.configure_namespace("repo_contributors", ttl_seconds=settings_ttl_minutes * 60)
    cache.configure_namespace("issue", ttl_seconds=300)
    cache.configure_namespace("issue_comments", ttl_seconds=300)
    cache.configure_namespace("issue_timeline", ttl_seconds=300)
    cache.configure_namespace("repo_content", ttl_seconds=3600)
    return cache


def make_client(settings: Settings | None = None) -> GitHubClient:
    """Create a GitHub API client from loaded settings."""
    effective_settings = settings or load_settings()
    return GitHubClient(
        token=effective_settings.github_token,
        cache=build_cache(effective_settings.cache_ttl_minutes),
    )
