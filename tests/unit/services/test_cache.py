from __future__ import annotations

import time

from gfi_scout.services.cache import NullCache, TTLNamespaceCache


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
