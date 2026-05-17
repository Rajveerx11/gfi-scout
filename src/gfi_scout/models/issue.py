"""Pydantic models for GitHub issues and the user-facing tool responses."""

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
    """Minimal slice of GitHub issue payloads used by tools and scoring."""

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
    comments: int | None = None
    pull_request: dict[str, object] | None = None


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
    beginner_score: int | None = None
    freshness: str | None = None
    repo_health_grade: str | None = None


class IssueStatus(BaseModel):
    """Result payload for the `check_issue_status` MCP tool."""

    model_config = ConfigDict(extra="forbid")

    issue_url: HttpUrl
    is_assigned: bool
    has_linked_pr: bool
    last_activity: datetime | None
    is_stale: bool
    competitor_prs: int
    maintainer_confirmed: bool
    availability_verdict: str
    notes: list[str] = Field(default_factory=list)


class ContributionGuide(BaseModel):
    """Result payload for the `get_contribution_guide` MCP tool."""

    model_config = ConfigDict(extra="forbid")

    repo_full_name: str
    contributing_summary: str
    setup_instructions: list[str]
    testing_requirements: list[str]
    pr_conventions: list[str]
    required_tools: list[str]
    setup_complexity: str
    source_files: list[str]
