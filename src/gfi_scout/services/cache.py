"""TTL caching backends for GitHub API responses."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Protocol, TypeVar, cast

from cachetools import TTLCache
from pydantic import BaseModel

from gfi_scout.models.issue import GitHubIssueRaw, SearchIssuesResponse
from gfi_scout.models.repo import RepoSummary
from gfi_scout.utils.logger import get_logger

T = TypeVar("T")

log = get_logger(__name__)

_MODEL_MARKER = "__gfi_scout_model__"
_MODEL_TYPES: dict[str, type[BaseModel]] = {
    f"{model_type.__module__}.{model_type.__qualname__}": model_type
    for model_type in (GitHubIssueRaw, RepoSummary, SearchIssuesResponse)
}
_SQLITE_WRITER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gfi-cache")


class Cache(Protocol):
    """Minimal cache surface — namespace + variadic key parts."""

    def get(self, namespace: str, *key_parts: object) -> object | None: ...
    def set(self, namespace: str, *key_parts: object, value: object) -> None: ...


class NullCache:
    """No-op cache. Every `get` is a miss; `set` is a no-op."""

    def get(self, namespace: str, *key_parts: object) -> object | None:  # noqa: ARG002
        return None

    def set(self, namespace: str, *key_parts: object, value: object) -> None:  # noqa: ARG002
        return None


def _composite_key(parts: tuple[object, ...]) -> str:
    return "|".join(str(p) for p in parts)


def _encode_value(value: object) -> object:
    if isinstance(value, BaseModel):
        model_name = f"{value.__class__.__module__}.{value.__class__.__qualname__}"
        if model_name not in _MODEL_TYPES:
            raise TypeError(f"Unsupported cached model: {model_name}")
        return {_MODEL_MARKER: model_name, "data": value.model_dump(mode="json")}
    if isinstance(value, list):
        return [_encode_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Cached dictionaries must use string keys")
        string_dict = cast(dict[str, object], value)
        return {key: _encode_value(item) for key, item in string_dict.items()}
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"Unsupported cached value: {type(value).__name__}")


def _decode_value(value: object) -> object:
    if isinstance(value, list):
        return [_decode_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("Cached dictionaries must use string keys")
        string_dict = cast(dict[str, object], value)
        model_name = string_dict.get(_MODEL_MARKER)
        if isinstance(model_name, str):
            model_type = _MODEL_TYPES.get(model_name)
            if model_type is None:
                raise ValueError(f"Unknown cached model: {model_name}")
            return model_type.model_validate(string_dict.get("data"))
        return {key: _decode_value(item) for key, item in string_dict.items()}
    return value


def _serialize(value: object) -> str:
    return json.dumps(_encode_value(value), separators=(",", ":"))


def _deserialize(payload: str) -> object:
    return _decode_value(cast(object, json.loads(payload)))


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


class SQLiteCache:
    """Persistent namespace cache with in-memory fallback on SQLite failures."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        partition: str = "anonymous",
        default_ttl_seconds: int = 1800,
        default_maxsize: int = 1024,
        sqlite_timeout_seconds: float = 0.05,
    ) -> None:
        self._path = path or Path.home() / ".cache" / "gfi-scout" / "cache.db"
        self._partition = partition
        self._default_ttl = default_ttl_seconds
        self._default_maxsize = default_maxsize
        self._sqlite_timeout = sqlite_timeout_seconds
        self._overrides: dict[str, tuple[int, int]] = {}
        self._entries: dict[tuple[str, str], tuple[object, float, float]] = {}
        self._entries_lock = Lock()
        self._invalidated_all = False
        self._invalidated_namespaces: set[str] = set()
        self._sqlite_enabled = True
        self._ready: Future[None] = _SQLITE_WRITER.submit(self._initialize)
        self._last_write: Future[None] | None = self._ready

    def _initialize(self) -> None:
        try:
            self._secure_cache_path()
            with self._connect() as connection:
                self._restrict_to_owner(self._path, 0o600)
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        partition TEXT NOT NULL,
                        namespace TEXT NOT NULL,
                        cache_key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        expires_at REAL NOT NULL,
                        accessed_at REAL NOT NULL,
                        PRIMARY KEY (partition, namespace, cache_key)
                    )
                    """
                )
                self._load_entries(connection)
        except (OSError, sqlite3.Error) as exc:
            self._disable_sqlite("initialize", exc)

    def _secure_cache_path(self) -> None:
        cache_directory = self._path.parent
        cache_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "posix":
            return
        if cache_directory.is_symlink() or self._path.is_symlink():
            raise OSError("SQLite cache path must not use symbolic links")
        self._restrict_to_owner(cache_directory, 0o700)
        if self._path.exists():
            self._restrict_to_owner(self._path, 0o600)

    @staticmethod
    def _restrict_to_owner(path: Path, mode: int) -> None:
        if os.name == "posix":
            path.chmod(mode)

    @property
    def path(self) -> Path:
        """Return the configured SQLite database path."""
        return self._path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=self._sqlite_timeout)

    def _load_entries(self, connection: sqlite3.Connection) -> None:
        now = time.time()
        rows = connection.execute(
            """
            SELECT namespace, cache_key, value, expires_at, accessed_at
            FROM cache_entries
            WHERE partition = ? AND expires_at > ?
            """,
            (self._partition, now),
        ).fetchall()
        loaded: dict[tuple[str, str], tuple[object, float, float]] = {}
        for row in rows:
            namespace, key, payload, expires_at, accessed_at = cast(
                tuple[str, str, str, float, float], row
            )
            try:
                value = _deserialize(payload)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                log.warning(
                    "Discarding unreadable SQLite cache entry ns=%s key=%s: %s",
                    namespace,
                    key,
                    exc,
                )
                continue
            loaded[(namespace, key)] = (value, expires_at, accessed_at)
        with self._entries_lock:
            for entry_key, entry in loaded.items():
                namespace, _ = entry_key
                if self._invalidated_all or namespace in self._invalidated_namespaces:
                    continue
                self._entries.setdefault(entry_key, entry)

    async def wait_ready(self) -> None:
        """Wait asynchronously until persisted entries have been hydrated."""
        await asyncio.shield(asyncio.wrap_future(self._ready))

    def _disable_sqlite(self, operation: str, exc: OSError | sqlite3.Error) -> None:
        if self._sqlite_enabled:
            log.warning(
                "SQLite cache %s failed at %s; using in-memory cache: %s",
                operation,
                self._path,
                exc,
            )
        self._sqlite_enabled = False

    def _settings(self, namespace: str) -> tuple[int, int]:
        return self._overrides.get(namespace, (self._default_ttl, self._default_maxsize))

    def configure_namespace(
        self,
        namespace: str,
        *,
        ttl_seconds: int,
        maxsize: int = 1024,
    ) -> None:
        """Set custom TTL/size for a namespace. Call before first use."""
        self._overrides[namespace] = (ttl_seconds, maxsize)
        with self._entries_lock:
            self._prune(namespace, maxsize)

    def _prune(self, namespace: str, maxsize: int) -> None:
        namespace_entries = sorted(
            (
                (key, entry[2])
                for (entry_namespace, key), entry in self._entries.items()
                if entry_namespace == namespace
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        for key, _ in namespace_entries[maxsize:]:
            self._entries.pop((namespace, key), None)

    def _submit_delete(self, namespace: str, key: str) -> None:
        if self._sqlite_enabled:
            self._last_write = _SQLITE_WRITER.submit(self._persist_delete, namespace, key)

    def _submit_touch(self, namespace: str, key: str, accessed_at: float) -> None:
        if self._sqlite_enabled:
            self._last_write = _SQLITE_WRITER.submit(
                self._persist_touch,
                namespace,
                key,
                accessed_at,
            )

    def get(self, namespace: str, *key_parts: object) -> object | None:
        key = _composite_key(key_parts)
        now = time.time()
        with self._entries_lock:
            entry = self._entries.get((namespace, key))
            if entry is None:
                return None
            value, expires_at, _ = entry
            if expires_at <= now:
                self._entries.pop((namespace, key), None)
                self._submit_delete(namespace, key)
                return None
            self._entries[(namespace, key)] = (value, expires_at, now)
        self._submit_touch(namespace, key, now)
        log.debug("cache hit ns=%s key=%s", namespace, key)
        return value

    def set(self, namespace: str, *key_parts: object, value: object) -> None:
        key = _composite_key(key_parts)
        ttl_seconds, maxsize = self._settings(namespace)
        now = time.time()
        with self._entries_lock:
            self._entries[(namespace, key)] = (value, now + ttl_seconds, now)
            self._prune(namespace, maxsize)
        if self._sqlite_enabled:
            self._last_write = _SQLITE_WRITER.submit(
                self._persist_set,
                namespace,
                key,
                value,
                now + ttl_seconds,
                now,
                maxsize,
            )
        log.debug("cache set ns=%s key=%s", namespace, key)

    def _persist_set(
        self,
        namespace: str,
        key: str,
        value: object,
        expires_at: float,
        accessed_at: float,
        maxsize: int,
    ) -> None:
        if not self._sqlite_enabled:
            return
        try:
            payload = _serialize(value)
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO cache_entries (
                        partition, namespace, cache_key, value, expires_at, accessed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(partition, namespace, cache_key) DO UPDATE SET
                        value = excluded.value,
                        expires_at = excluded.expires_at,
                        accessed_at = excluded.accessed_at
                    """,
                    (self._partition, namespace, key, payload, expires_at, accessed_at),
                )
                connection.execute(
                    "DELETE FROM cache_entries WHERE partition = ? AND expires_at <= ?",
                    (self._partition, time.time()),
                )
                connection.execute(
                    """
                    DELETE FROM cache_entries
                    WHERE partition = ? AND namespace = ? AND cache_key IN (
                        SELECT cache_key FROM cache_entries
                        WHERE partition = ? AND namespace = ?
                        ORDER BY accessed_at DESC
                        LIMIT -1 OFFSET ?
                    )
                    """,
                    (self._partition, namespace, self._partition, namespace, maxsize),
                )
        except (TypeError, ValueError) as exc:
            log.warning(
                "Skipping unsupported SQLite cache value ns=%s key=%s: %s",
                namespace,
                key,
                exc,
            )
        except sqlite3.Error as exc:
            self._disable_sqlite("write", exc)

    def _persist_delete(self, namespace: str, key: str) -> None:
        if not self._sqlite_enabled:
            return
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    DELETE FROM cache_entries
                    WHERE partition = ? AND namespace = ? AND cache_key = ?
                    """,
                    (self._partition, namespace, key),
                )
        except sqlite3.Error as exc:
            self._disable_sqlite("delete", exc)

    def _persist_touch(self, namespace: str, key: str, accessed_at: float) -> None:
        if not self._sqlite_enabled:
            return
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE cache_entries SET accessed_at = ?
                    WHERE partition = ? AND namespace = ? AND cache_key = ?
                    """,
                    (accessed_at, self._partition, namespace, key),
                )
        except sqlite3.Error as exc:
            self._disable_sqlite("touch", exc)

    def invalidate(self, namespace: str | None = None) -> None:
        """Remove one namespace or all entries from both cache backends."""
        with self._entries_lock:
            if namespace is None:
                self._invalidated_all = True
                self._entries.clear()
            else:
                self._invalidated_namespaces.add(namespace)
                for entry_namespace, key in list(self._entries):
                    if entry_namespace == namespace:
                        self._entries.pop((entry_namespace, key), None)
        if not self._sqlite_enabled:
            return
        self._last_write = _SQLITE_WRITER.submit(self._persist_invalidate, namespace)

    def _persist_invalidate(self, namespace: str | None) -> None:
        if not self._sqlite_enabled:
            return
        try:
            with self._connect() as connection:
                if namespace is None:
                    connection.execute(
                        "DELETE FROM cache_entries WHERE partition = ?",
                        (self._partition,),
                    )
                else:
                    connection.execute(
                        "DELETE FROM cache_entries WHERE partition = ? AND namespace = ?",
                        (self._partition, namespace),
                    )
        except sqlite3.Error as exc:
            self._disable_sqlite("invalidate", exc)

    def flush(self, timeout_seconds: float = 5.0) -> None:
        """Wait for queued persistence work; intended for tests and orderly shutdown."""
        if self._last_write is not None:
            self._last_write.result(timeout=timeout_seconds)
