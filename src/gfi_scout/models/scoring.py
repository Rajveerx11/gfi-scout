"""Scoring models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScoreBreakdown(BaseModel):
    """Per-component scores that compose the beginner_score.

    Each sub-score is normalised to 0..100. The final composite is computed
    by `services.issue_scorer.compute_beginner_score` using the weights in
    `config/scoring_weights.json`.
    """

    model_config = ConfigDict(extra="forbid")

    repo_health: float = Field(ge=0, le=100)
    issue_freshness: float = Field(ge=0, le=100)
    issue_clarity: float = Field(ge=0, le=100)
    merge_friendliness: float = Field(ge=0, le=100)
    setup_complexity_inv: float = Field(ge=0, le=100)


class BeginnerScore(BaseModel):
    """Composite beginner-friendliness score (0-100) with breakdown + grade."""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=100)
    grade: str
    breakdown: ScoreBreakdown
    explanation: str
