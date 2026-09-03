"""Typed models for issue-claim detection."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClaimPhraseConfig(BaseModel):
    """Validated phrases and author roles used for claim detection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_phrases: tuple[str, ...] = Field(min_length=1)
    maintainer_confirmation_phrases: tuple[str, ...] = Field(min_length=1)
    maintainer_associations: frozenset[str] = Field(min_length=1)
    recent_comment_limit: int = Field(gt=0, le=100)


class ClaimDetection(BaseModel):
    """Claim and maintainer-confirmation signals found in issue comments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_detected: bool
    maintainer_confirmed: bool
