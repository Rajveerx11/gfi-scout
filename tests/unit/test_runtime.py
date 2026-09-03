from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from gfi_scout import runtime
from gfi_scout.config import Settings
from gfi_scout.runtime import _credential_partition, build_cache
from gfi_scout.services.cache import SQLiteCache, TTLNamespaceCache


def test_build_cache_defaults_to_memory() -> None:
    assert isinstance(build_cache(30), TTLNamespaceCache)


def test_build_cache_can_enable_sqlite(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"

    cache = build_cache(30, backend="sqlite", sqlite_path=database)

    assert isinstance(cache, SQLiteCache)
    assert cache.path == database


def test_sqlite_cache_partitions_entries_by_credential(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    first_token = "secret-token-one"
    first = build_cache(
        30,
        backend="sqlite",
        sqlite_path=database,
        credential_partition=_credential_partition(first_token),
    )
    assert isinstance(first, SQLiteCache)
    first.set("repo", "private/widgets", value="private data")
    first.flush()

    second = build_cache(
        30,
        backend="sqlite",
        sqlite_path=database,
        credential_partition=_credential_partition("secret-token-two"),
    )
    same_credential = build_cache(
        30,
        backend="sqlite",
        sqlite_path=database,
        credential_partition=_credential_partition(first_token),
    )
    assert isinstance(second, SQLiteCache)
    assert isinstance(same_credential, SQLiteCache)
    second.flush()
    same_credential.flush()

    assert second.get("repo", "private/widgets") is None
    assert same_credential.get("repo", "private/widgets") == "private data"
    assert first_token.encode() not in database.read_bytes()


async def test_make_client_waits_for_restart_hydration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "cache.db"
    first = SQLiteCache(database, partition="partition")
    first.set("repo", "acme/widgets", value="persisted")
    first.flush()

    locker = sqlite3.connect(database)
    try:
        locker.execute("BEGIN EXCLUSIVE")
        restarted = SQLiteCache(
            database,
            partition="partition",
            sqlite_timeout_seconds=0.5,
        )
        monkeypatch.setattr(runtime, "_runtime_cache", lambda settings: restarted)
        settings = Settings(
            github_token="token",
            cache_ttl_minutes=30,
            log_level="info",
            max_concurrent_requests=5,
            cache_backend="sqlite",
        )

        async def read_after_enter() -> object | None:
            async with runtime.make_client(settings):
                return restarted.get("repo", "acme/widgets")

        read_task = asyncio.create_task(read_after_enter())
        await asyncio.sleep(0.01)
        assert not read_task.done()
        locker.rollback()

        assert await read_task == "persisted"
    finally:
        locker.close()
