"""Load and validate `config/scoring_weights.json` into a typed object."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "scoring_weights.json"


class ScoringConfigError(RuntimeError):
    """Raised when scoring config is missing or malformed."""


@dataclass(frozen=True)
class ScoringConfig:
    # weights
    w_repo_health: float
    w_issue_freshness: float
    w_issue_clarity: float
    w_merge_friendliness: float
    w_setup_complexity_inv: float
    # thresholds
    stale_issue_days: int
    fresh_issue_days: int
    clarity_min_body_chars: int
    clarity_great_body_chars: int
    active_repo_commit_days: int
    stale_repo_commit_days: int
    high_merge_rate: float
    low_merge_rate: float
    # grades
    grade_a: int
    grade_b: int
    grade_c: int
    grade_d: int


def _require_float(d: dict[str, object], key: str) -> float:
    v = d.get(key)
    if not isinstance(v, (int, float)):
        raise ScoringConfigError(f"weights.{key} must be a number, got {v!r}")
    return float(v)


def _require_int(d: dict[str, object], key: str) -> int:
    v = d.get(key)
    if not isinstance(v, int) or isinstance(v, bool):
        raise ScoringConfigError(f"thresholds.{key} must be int, got {v!r}")
    return v


def load_scoring_config(path: Path | None = None) -> ScoringConfig:
    cfg_path = path or DEFAULT_PATH
    if not cfg_path.exists():
        raise ScoringConfigError(f"scoring config not found: {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as fp:
        raw = json.load(fp)
    weights = raw.get("weights")
    thresholds = raw.get("thresholds")
    grades = raw.get("grade_cutoffs")
    if (
        not isinstance(weights, dict)
        or not isinstance(thresholds, dict)
        or not isinstance(grades, dict)
    ):
        raise ScoringConfigError("scoring config missing weights/thresholds/grades")

    total = sum(
        _require_float(weights, k)
        for k in (
            "repo_health",
            "issue_freshness",
            "issue_clarity",
            "merge_friendliness",
            "setup_complexity_inv",
        )
    )
    if not 0.99 <= total <= 1.01:
        raise ScoringConfigError(f"weights must sum to 1.0 (got {total:.3f})")

    return ScoringConfig(
        w_repo_health=_require_float(weights, "repo_health"),
        w_issue_freshness=_require_float(weights, "issue_freshness"),
        w_issue_clarity=_require_float(weights, "issue_clarity"),
        w_merge_friendliness=_require_float(weights, "merge_friendliness"),
        w_setup_complexity_inv=_require_float(weights, "setup_complexity_inv"),
        stale_issue_days=_require_int(thresholds, "stale_issue_days"),
        fresh_issue_days=_require_int(thresholds, "fresh_issue_days"),
        clarity_min_body_chars=_require_int(thresholds, "clarity_min_body_chars"),
        clarity_great_body_chars=_require_int(thresholds, "clarity_great_body_chars"),
        active_repo_commit_days=_require_int(thresholds, "active_repo_commit_days"),
        stale_repo_commit_days=_require_int(thresholds, "stale_repo_commit_days"),
        high_merge_rate=_require_float(thresholds, "high_merge_rate"),
        low_merge_rate=_require_float(thresholds, "low_merge_rate"),
        grade_a=_require_int(grades, "A"),
        grade_b=_require_int(grades, "B"),
        grade_c=_require_int(grades, "C"),
        grade_d=_require_int(grades, "D"),
    )


@lru_cache(maxsize=1)
def get_scoring_config() -> ScoringConfig:
    return load_scoring_config()
