from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gfi_scout.models.issue import GitHubIssueRaw
from gfi_scout.models.repo import RepoHealth
from gfi_scout.services.issue_scorer import (
    compute_beginner_score,
    freshness_label,
    issue_clarity_subscore,
    issue_freshness_subscore,
    merge_friendliness_subscore,
    repo_health_subscore,
    setup_complexity_inv_subscore,
)
from gfi_scout.services.scoring_config import get_scoring_config


def _make_issue(
    *,
    body: str = "Add tests for parser. Steps to reproduce: run pytest.",
    age_days: int = 5,
) -> GitHubIssueRaw:
    now = datetime.now(UTC)
    when = now - timedelta(days=age_days)
    return GitHubIssueRaw.model_validate(
        {
            "title": "test",
            "html_url": "https://github.com/a/b/issues/1",
            "body": body,
            "repository_url": "https://api.github.com/repos/a/b",
            "labels": [{"name": "good first issue"}],
            "assignee": None,
            "assignees": [],
            "created_at": when.isoformat(),
            "updated_at": when.isoformat(),
        }
    )


def _make_health(
    grade: str = "A", merge_rate: float = 0.8, has_contributing: bool = True, has_ci: bool = True
) -> RepoHealth:
    return RepoHealth(
        repo_full_name="a/b",
        merge_rate=merge_rate,
        avg_review_time_hours=12.0,
        avg_merge_time_hours=48.0,
        maintainer_response_time_hours=12.0,
        last_commit_date=datetime.now(UTC),
        active_contributors_30d=15,
        has_contributing_guide=has_contributing,
        has_code_of_conduct=True,
        ci_configured=has_ci,
        health_grade=grade,
    )


@pytest.fixture
def cfg():
    return get_scoring_config()


class TestFreshnessSubscore:
    def test_fresh_issue(self, cfg) -> None:
        issue = _make_issue(age_days=3)
        assert issue_freshness_subscore(issue, cfg) == 100.0

    def test_stale_issue(self, cfg) -> None:
        issue = _make_issue(age_days=120)
        assert issue_freshness_subscore(issue, cfg) == 0.0

    def test_middle_bucket(self, cfg) -> None:
        issue = _make_issue(age_days=30)
        score = issue_freshness_subscore(issue, cfg)
        assert 20.0 < score < 90.0


class TestClaritySubscore:
    def test_empty_body(self, cfg) -> None:
        issue = _make_issue(body="")
        assert issue_clarity_subscore(issue, cfg) == 0.0

    def test_long_body_gets_high_score(self, cfg) -> None:
        issue = _make_issue(body="x" * 500 + "\n```python\nprint(1)\n```")
        assert issue_clarity_subscore(issue, cfg) >= 95.0

    def test_short_body_gets_low_base(self, cfg) -> None:
        issue = _make_issue(body="fix it")
        score = issue_clarity_subscore(issue, cfg)
        assert score <= 50.0


class TestMergeFriendliness:
    def test_high_merge_rate(self, cfg) -> None:
        assert merge_friendliness_subscore(_make_health(merge_rate=0.9), cfg) == 100.0

    def test_low_merge_rate(self, cfg) -> None:
        assert merge_friendliness_subscore(_make_health(merge_rate=0.1), cfg) == 15.0

    def test_none_defaults_to_50(self, cfg) -> None:
        assert merge_friendliness_subscore(None, cfg) == 50.0


class TestRepoHealthSubscore:
    def test_grade_a_is_high(self) -> None:
        assert repo_health_subscore(_make_health("A")) >= 90.0

    def test_grade_f_is_low(self) -> None:
        assert repo_health_subscore(_make_health("F")) <= 20.0

    def test_none(self) -> None:
        assert repo_health_subscore(None) == 50.0


class TestSetupComplexityInv:
    def test_full_signals(self) -> None:
        score = setup_complexity_inv_subscore(
            _make_health(has_contributing=True, has_ci=True),
        )
        assert score == 100.0

    def test_missing_everything(self) -> None:
        score = setup_complexity_inv_subscore(
            _make_health(has_contributing=False, has_ci=False),
        )
        assert score <= 50.0


class TestComposite:
    def test_great_repo_great_issue(self, cfg) -> None:
        issue = _make_issue(age_days=2, body="x" * 500 + "\nSteps to reproduce: run pytest.")
        result = compute_beginner_score(issue, _make_health("A"), cfg=cfg)
        assert result.score >= 85
        assert result.grade == "A"

    def test_dead_repo_stale_issue(self, cfg) -> None:
        issue = _make_issue(age_days=120, body="")
        result = compute_beginner_score(issue, _make_health("F", merge_rate=0.05), cfg=cfg)
        assert result.score < 40
        assert result.grade == "F"

    def test_freshness_label(self, cfg) -> None:
        assert freshness_label(_make_issue(age_days=3), cfg) == "fresh"
        assert freshness_label(_make_issue(age_days=30), cfg) == "warm"
        assert freshness_label(_make_issue(age_days=120), cfg) == "stale"
