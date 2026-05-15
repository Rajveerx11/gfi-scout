"""Beginner-score computation.

Combines per-issue freshness/clarity signals with per-repo health into a
single composite (0-100). All weights and thresholds live in
`config/scoring_weights.json`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from gfi_scout.models.issue import GitHubIssueRaw
from gfi_scout.models.repo import RepoHealth
from gfi_scout.models.scoring import BeginnerScore, ScoreBreakdown
from gfi_scout.services.scoring_config import ScoringConfig

GRADE_TO_SCORE = {"A": 95.0, "B": 80.0, "C": 60.0, "D": 40.0, "F": 15.0}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def repo_health_subscore(health: RepoHealth | None) -> float:
    if health is None:
        return 50.0
    return GRADE_TO_SCORE.get(health.health_grade, 40.0)


def issue_freshness_subscore(issue: GitHubIssueRaw, cfg: ScoringConfig) -> float:
    age_days = (_now() - _to_utc(issue.updated_at)).days
    if age_days <= cfg.fresh_issue_days:
        return 100.0
    if age_days >= cfg.stale_issue_days:
        return 0.0
    span = cfg.stale_issue_days - cfg.fresh_issue_days
    progress = (age_days - cfg.fresh_issue_days) / span
    return max(0.0, 100.0 * (1.0 - progress))


def issue_clarity_subscore(issue: GitHubIssueRaw, cfg: ScoringConfig) -> float:
    body = (issue.body or "").strip()
    length = len(body)
    if length == 0:
        return 0.0
    if length >= cfg.clarity_great_body_chars:
        base = 100.0
    elif length <= cfg.clarity_min_body_chars:
        base = 30.0
    else:
        span = cfg.clarity_great_body_chars - cfg.clarity_min_body_chars
        progress = (length - cfg.clarity_min_body_chars) / span
        base = 30.0 + (70.0 * progress)

    # Bonuses for structure cues a beginner can actually use.
    bonus = 0.0
    lowered = body.lower()
    if "```" in body:
        bonus += 5.0
    if "steps to reproduce" in lowered or "to reproduce" in lowered:
        bonus += 5.0
    if any(token in lowered for token in ("hint", "see ", "example")):
        bonus += 2.5
    return min(100.0, base + bonus)


def merge_friendliness_subscore(health: RepoHealth | None, cfg: ScoringConfig) -> float:
    if health is None or health.merge_rate is None:
        return 50.0
    rate = health.merge_rate
    if rate >= cfg.high_merge_rate:
        return 100.0
    if rate <= cfg.low_merge_rate:
        return 15.0
    span = cfg.high_merge_rate - cfg.low_merge_rate
    progress = (rate - cfg.low_merge_rate) / span
    return 15.0 + (85.0 * progress)


def setup_complexity_inv_subscore(health: RepoHealth | None) -> float:
    """Approximate the inverse of setup complexity.

    Phase 2 proxy: a repo with CONTRIBUTING.md + CI configured is far more
    likely to have reproducible local setup than one without. The Phase 3
    `get_contribution_guide` tool refines this with a parsed estimate.
    """
    if health is None:
        return 50.0
    score = 30.0
    if health.has_contributing_guide:
        score += 35.0
    if health.ci_configured:
        score += 25.0
    if health.has_code_of_conduct:
        score += 10.0
    return min(100.0, score)


def _grade_from_score(score: int, cfg: ScoringConfig) -> str:
    if score >= cfg.grade_a:
        return "A"
    if score >= cfg.grade_b:
        return "B"
    if score >= cfg.grade_c:
        return "C"
    if score >= cfg.grade_d:
        return "D"
    return "F"


def compute_beginner_score(
    issue: GitHubIssueRaw,
    health: RepoHealth | None,
    *,
    cfg: ScoringConfig,
) -> BeginnerScore:
    breakdown = ScoreBreakdown(
        repo_health=repo_health_subscore(health),
        issue_freshness=issue_freshness_subscore(issue, cfg),
        issue_clarity=issue_clarity_subscore(issue, cfg),
        merge_friendliness=merge_friendliness_subscore(health, cfg),
        setup_complexity_inv=setup_complexity_inv_subscore(health),
    )
    weighted = (
        breakdown.repo_health * cfg.w_repo_health
        + breakdown.issue_freshness * cfg.w_issue_freshness
        + breakdown.issue_clarity * cfg.w_issue_clarity
        + breakdown.merge_friendliness * cfg.w_merge_friendliness
        + breakdown.setup_complexity_inv * cfg.w_setup_complexity_inv
    )
    score = int(round(max(0.0, min(100.0, weighted))))
    grade = _grade_from_score(score, cfg)
    explanation = (
        f"repo_health={breakdown.repo_health:.0f} "
        f"freshness={breakdown.issue_freshness:.0f} "
        f"clarity={breakdown.issue_clarity:.0f} "
        f"merge_rate={breakdown.merge_friendliness:.0f} "
        f"setup={breakdown.setup_complexity_inv:.0f}"
    )
    return BeginnerScore(
        score=score, grade=grade, breakdown=breakdown, explanation=explanation,
    )


def freshness_label(issue: GitHubIssueRaw, cfg: ScoringConfig) -> str:
    age_days = (_now() - _to_utc(issue.updated_at)).days
    if age_days <= cfg.fresh_issue_days:
        return "fresh"
    if age_days <= cfg.stale_issue_days:
        return "warm"
    return "stale"
