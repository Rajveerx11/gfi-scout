from __future__ import annotations

import pytest

from gfi_scout.config import ConfigError, load_settings


def test_cache_backend_defaults_to_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CACHE_BACKEND", raising=False)

    assert load_settings().cache_backend == "memory"


def test_cache_backend_accepts_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_BACKEND", "sqlite")

    assert load_settings().cache_backend == "sqlite"


def test_cache_backend_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_BACKEND", "redis")

    with pytest.raises(ConfigError, match="CACHE_BACKEND"):
        load_settings()
