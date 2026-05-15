"""Repository-related Pydantic models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RepoSummary(BaseModel):
    """Lightweight repo metadata used by tools and scoring."""

    model_config = ConfigDict(extra="ignore")

    full_name: str
    stars: int | None = None
    language: str | None = None
    default_branch: str | None = None
    pushed_at: datetime | None = None
    open_issues_count: int | None = None
    topics: list[str] = Field(default_factory=list)


class RepoHealth(BaseModel):
    """Result payload for the `check_repo_health` MCP tool."""

    model_config = ConfigDict(extra="forbid")

    repo_full_name: str
    merge_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    avg_review_time_hours: float | None = None
    avg_merge_time_hours: float | None = None
    maintainer_response_time_hours: float | None = None
    last_commit_date: datetime | None = None
    active_contributors_30d: int | None = None
    has_contributing_guide: bool
    has_code_of_conduct: bool
    ci_configured: bool
    health_grade: str
    notes: list[str] = Field(default_factory=list)
