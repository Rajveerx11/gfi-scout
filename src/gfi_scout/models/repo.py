"""Repository-related Pydantic models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RepoSummary(BaseModel):
    """Minimal repo fields used by Phase 1."""

    model_config = ConfigDict(extra="ignore")

    full_name: str
    stars: int | None = None
    language: str | None = None
    default_branch: str | None = None
