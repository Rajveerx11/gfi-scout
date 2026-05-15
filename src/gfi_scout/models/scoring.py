"""Scoring models (Phase 1 placeholder)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BeginnerScore(BaseModel):
    """Composite beginner-friendliness score. Real computation lands in Phase 2."""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(default=0, ge=0, le=100)
    explanation: str = "Phase 1 placeholder — scoring engine arrives in Phase 2."
