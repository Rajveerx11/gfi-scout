from __future__ import annotations

import json
from pathlib import Path

import pytest

from gfi_scout.services.scoring_config import (
    ScoringConfigError,
    load_scoring_config,
)


def _write(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "weights.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_default_config_succeeds() -> None:
    cfg = load_scoring_config()
    total = (
        cfg.w_repo_health
        + cfg.w_issue_freshness
        + cfg.w_issue_clarity
        + cfg.w_merge_friendliness
        + cfg.w_setup_complexity_inv
    )
    assert abs(total - 1.0) < 0.01


def test_rejects_missing_section(tmp_path: Path) -> None:
    p = _write(tmp_path, {"weights": {}})
    with pytest.raises(ScoringConfigError):
        load_scoring_config(p)


def test_rejects_weights_not_summing_to_one(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "weights": {
                "repo_health": 0.5,
                "issue_freshness": 0.5,
                "issue_clarity": 0.5,
                "merge_friendliness": 0.5,
                "setup_complexity_inv": 0.5,
            },
            "thresholds": {
                "stale_issue_days": 60,
                "fresh_issue_days": 14,
                "clarity_min_body_chars": 80,
                "clarity_great_body_chars": 400,
                "active_repo_commit_days": 7,
                "stale_repo_commit_days": 90,
                "high_merge_rate": 0.7,
                "low_merge_rate": 0.2,
            },
            "grade_cutoffs": {"A": 85, "B": 70, "C": 55, "D": 40},
        },
    )
    with pytest.raises(ScoringConfigError):
        load_scoring_config(p)


def test_rejects_bad_threshold_type(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "weights": {
                "repo_health": 0.30,
                "issue_freshness": 0.20,
                "issue_clarity": 0.15,
                "merge_friendliness": 0.25,
                "setup_complexity_inv": 0.10,
            },
            "thresholds": {
                "stale_issue_days": "sixty",
                "fresh_issue_days": 14,
                "clarity_min_body_chars": 80,
                "clarity_great_body_chars": 400,
                "active_repo_commit_days": 7,
                "stale_repo_commit_days": 90,
                "high_merge_rate": 0.7,
                "low_merge_rate": 0.2,
            },
            "grade_cutoffs": {"A": 85, "B": 70, "C": 55, "D": 40},
        },
    )
    with pytest.raises(ScoringConfigError):
        load_scoring_config(p)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ScoringConfigError):
        load_scoring_config(tmp_path / "missing.json")
