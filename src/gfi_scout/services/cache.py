"""TTL caching layer for GitHub API responses.

The cache lives in-memory (`cachetools.TTLCache`) and is keyed by a caller-
supplied namespace plus arbitrary key segments. Each namespace gets its own
bucket so a high-churn space (issue searches) cannot evict a slower-changing
one (repo health snapshots).
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from cachetools import TTLCache

from gfi_scout.utils.logger import get_logger

T = TypeVar("T")

log = get_logger(__name__)


class Cache(Protocol):
    """Minimal cache surface — get / set with string keys."""

    def get(self, key: str) -> object | None: ...
    def set(self, key: str, value: object) -> None: ...


class NullCache:
    """No-op cache. Every `get` is a miss; `set` is a no-op."""

    def get(self, key: str) -> object | None:  # noqa: ARG002
        return None

    def set(self, key: str, value: object) -> None:  # noqa: ARG002
        return None


def _composite_key(parts: tuple[object, ...]) -> str:
    return "|".join(str(p) for p in parts)


class TTLNamespaceCache:
    """In-memory TTL cache partitioned by namespace.

    Each namespace gets its own `TTLCache` so heavy-traffic spaces (e.g.
    issue searches) cannot evict slower-changing entries (repo health).
    """

    def __init__(
        self,
        *,
        default_ttl_seconds: int = 1800,
        default_maxsize: int = 1024,
    ) -> None:
        self._default_ttl = default_ttl_seconds
        self._default_maxsize = default_maxsize
        self._buckets: dict[str, TTLCache[str, object]] = {}
        self._overrides: dict[str, tuple[int, int]] = {}

    def configure_namespace(
        self,
        namespace: str,
        *,
        ttl_seconds: int,
        maxsize: int = 1024,
    ) -> None:
        """Set custom TTL/size for a namespace. Call before first use."""
        self._overrides[namespace] = (ttl_seconds, maxsize)
        # Drop any existing bucket so new config takes effect.
        self._buckets.pop(namespace, None)

    def _bucket(self, namespace: str) -> TTLCache[str, object]:
        bucket = self._buckets.get(namespace)
        if bucket is None:
            ttl, maxsize = self._overrides.get(
                namespace, (self._default_ttl, self._default_maxsize)
            )
            bucket = TTLCache(maxsize=maxsize, ttl=ttl)
            self._buckets[namespace] = bucket
        return bucket

    def get(self, namespace: str, *key_parts: object) -> object | None:
        key = _composite_key(key_parts)
        try:
            value = self._bucket(namespace).get(key)
        except KeyError:
            return None
        if value is not None:
            log.debug("cache hit ns=%s key=%s", namespace, key)
        return value

    def set(self, namespace: str, *key_parts: object, value: object) -> None:
        key = _composite_key(key_parts)
        self._bucket(namespace)[key] = value
        log.debug("cache set ns=%s key=%s", namespace, key)

    def invalidate(self, namespace: str | None = None) -> None:
        if namespace is None:
            self._buckets.clear()
        else:
            self._buckets.pop(namespace, None)
