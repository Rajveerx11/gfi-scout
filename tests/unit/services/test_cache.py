from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path

import pytest

from gfi_scout.models.repo import RepoSummary
from gfi_scout.services.cache import NullCache, SQLiteCache, TTLNamespaceCache


def test_null_cache_returns_none_and_set_is_noop() -> None:
    cache = NullCache()
    cache.set("ns", "k", value="v")
    assert cache.get("ns", "k") is None


def test_ttl_cache_round_trip() -> None:
    cache = TTLNamespaceCache(default_ttl_seconds=60)
    cache.set("ns", "a", "b", value=123)
    assert cache.get("ns", "a", "b") == 123
    assert cache.get("ns", "a", "c") is None


def test_ttl_cache_namespace_isolation() -> None:
    cache = TTLNamespaceCache(default_ttl_seconds=60)
    cache.set("ns1", "key", value="x")
    cache.set("ns2", "key", value="y")
    assert cache.get("ns1", "key") == "x"
    assert cache.get("ns2", "key") == "y"


def test_ttl_cache_expiry() -> None:
    cache = TTLNamespaceCache(default_ttl_seconds=60)
    cache.configure_namespace("short", ttl_seconds=1, maxsize=8)
    cache.set("short", "k", value="v")
    assert cache.get("short", "k") == "v"
    time.sleep(1.05)
    assert cache.get("short", "k") is None


def test_invalidate_namespace() -> None:
    cache = TTLNamespaceCache()
    cache.set("ns", "k", value=1)
    cache.invalidate("ns")
    assert cache.get("ns", "k") is None


def test_invalidate_all() -> None:
    cache = TTLNamespaceCache()
    cache.set("a", "k", value=1)
    cache.set("b", "k", value=2)
    cache.invalidate()
    assert cache.get("a", "k") is None
    assert cache.get("b", "k") is None


async def test_sqlite_cache_is_ready_immediately_after_restart(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    expected = [RepoSummary(full_name="acme/widgets", stars=42)]

    first = SQLiteCache(database, default_ttl_seconds=60)
    first.set("repos", "python", value=expected)
    first.flush()
    second = SQLiteCache(database, default_ttl_seconds=60)
    await second.wait_ready()

    assert second.get("repos", "python") == expected


def test_sqlite_cache_respects_expiry_across_instances(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    first = SQLiteCache(database, default_ttl_seconds=1)
    first.set("ns", "key", value="value")
    first.flush()

    time.sleep(1.05)
    second = SQLiteCache(database, default_ttl_seconds=60)
    second.flush()

    assert second.get("ns", "key") is None


def test_sqlite_cache_keeps_namespaces_isolated(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    first = SQLiteCache(database)
    first.set("one", "key", value=1)
    first.set("two", "key", value=2)
    first.flush()

    second = SQLiteCache(database)
    second.flush()

    assert second.get("one", "key") == 1
    assert second.get("two", "key") == 2


def test_corrupt_sqlite_cache_falls_back_to_memory(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    database.write_bytes(b"not a sqlite database")

    cache = SQLiteCache(database)
    cache.set("ns", "key", value="memory value")
    cache.flush()

    assert cache.get("ns", "key") == "memory value"


def test_locked_sqlite_cache_falls_back_to_memory(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    with sqlite3.connect(database) as locker:
        locker.execute("CREATE TABLE lock_holder (value TEXT)")
        locker.execute("BEGIN EXCLUSIVE")
        locker.execute("INSERT INTO lock_holder VALUES ('held')")

        cache = SQLiteCache(database, sqlite_timeout_seconds=0.001)
        cache.flush()
        cache.set("ns", "key", value="memory value")

        assert cache.get("ns", "key") == "memory value"


async def test_sqlite_contention_does_not_block_event_loop(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    cache = SQLiteCache(database, sqlite_timeout_seconds=0.5)
    cache.flush()

    with sqlite3.connect(database) as locker:
        locker.execute("BEGIN EXCLUSIVE")
        started = time.perf_counter()
        heartbeat = asyncio.create_task(asyncio.sleep(0.01))

        cache.set("ns", "key", value="value")
        await heartbeat

        assert time.perf_counter() - started < 0.1

    cache.flush()


async def test_sqlite_initialization_does_not_block_event_loop(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    with sqlite3.connect(database) as locker:
        locker.execute("CREATE TABLE lock_holder (value TEXT)")
        locker.execute("BEGIN EXCLUSIVE")
        locker.execute("INSERT INTO lock_holder VALUES ('held')")
        started = time.perf_counter()
        heartbeat = asyncio.create_task(asyncio.sleep(0.01))

        cache = SQLiteCache(database, sqlite_timeout_seconds=0.5)
        await heartbeat

        assert time.perf_counter() - started < 0.1

    cache.flush()


async def test_invalidate_during_hydration_cannot_restore_stale_rows(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    first = SQLiteCache(database)
    first.set("ns", "key", value="stale")
    first.flush()

    locker = sqlite3.connect(database)
    try:
        locker.execute("BEGIN EXCLUSIVE")
        restarted = SQLiteCache(database, sqlite_timeout_seconds=0.5)
        restarted.invalidate("ns")
        locker.rollback()

        await restarted.wait_ready()
        assert restarted.get("ns", "key") is None
        restarted.flush()
    finally:
        locker.close()

    final = SQLiteCache(database)
    await final.wait_ready()
    assert final.get("ns", "key") is None


async def test_cancelled_ready_waiter_does_not_poison_shared_cache(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    first = SQLiteCache(database)
    first.set("ns", "key", value="persisted")
    first.flush()

    locker = sqlite3.connect(database)
    try:
        locker.execute("BEGIN EXCLUSIVE")
        restarted = SQLiteCache(database, sqlite_timeout_seconds=0.5)
        cancelled_waiter = asyncio.create_task(restarted.wait_ready())
        await asyncio.sleep(0.01)
        cancelled_waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled_waiter
        locker.rollback()

        await restarted.wait_ready()
        assert restarted.get("ns", "key") == "persisted"
    finally:
        locker.close()
