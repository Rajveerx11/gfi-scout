"""Pydantic models for GitHub issues and the user-facing tool response."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class GitHubLabel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str


class GitHubUser(BaseModel):
    model_config = ConfigDict(extra="ignore")
    login: str


class GitHubIssueRaw(BaseModel):
    """Minimal slice of the GitHub Search API issue object we actually use."""

    model_config = ConfigDict(extra="ignore")

    title: str
    html_url: HttpUrl
    body: str | None = None
    repository_url: HttpUrl
    labels: list[GitHubLabel] = Field(default_factory=list)
    assignee: GitHubUser | None = None
    assignees: list[GitHubUser] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SearchIssuesResponse(BaseModel):
    """Typed wrapper around GET /search/issues."""

    model_config = ConfigDict(extra="ignore")

    total_count: int
    incomplete_results: bool
    items: list[GitHubIssueRaw]


class IssueResult(BaseModel):
    """User-facing issue payload returned by the `find_issues` MCP tool."""

    model_config = ConfigDict(extra="forbid")

    title: str
    url: HttpUrl
    body_preview: str
    repo_full_name: str
    repo_stars: int | None = None
    repo_language: str | None = None
    labels: list[str]
    is_assigned: bool
    created_at: datetime
    updated_at: datetime
