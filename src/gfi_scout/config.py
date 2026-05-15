"""Runtime configuration loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


@dataclass(frozen=True)
class Settings:
    github_token: str
    cache_ttl_minutes: int
    log_level: str
    max_concurrent_requests: int


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(
            f"Missing required environment variable: {name}. "
            "Copy .env.example to .env and populate it."
        )
    return value


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer, got: {raw!r}") from exc


def load_settings() -> Settings:
    return Settings(
        github_token=_required("GITHUB_TOKEN"),
        cache_ttl_minutes=_int("CACHE_TTL_MINUTES", 30),
        log_level=os.getenv("LOG_LEVEL", "info"),
        max_concurrent_requests=_int("MAX_CONCURRENT_REQUESTS", 5),
    )
