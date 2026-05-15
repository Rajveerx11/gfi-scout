"""Cache interface (Phase 1 stub).

A real `cachetools.TTLCache` implementation arrives in Phase 2 to back the
rate-limit-aware request layer. For now we ship a typed Protocol + a no-op
implementation so callers can wire against the interface without behaviour
changes.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

T = TypeVar("T")


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
