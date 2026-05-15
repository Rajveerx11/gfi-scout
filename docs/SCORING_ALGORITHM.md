# Scoring Algorithm

GFI Scout's job is to rank "good first issue" candidates by how likely a
beginner is to *actually succeed* — not just find. This page documents how
that ranking is computed.

All weights and thresholds live in [`config/scoring_weights.json`](../config/scoring_weights.json).
There are no magic numbers in the Python code; if you want to retune the
ranker, edit that file.

## Composite formula

```
beginner_score = repo_health        × 0.30
               + issue_freshness    × 0.20
               + issue_clarity      × 0.15
               + merge_friendliness × 0.25
               + setup_complexity_inv × 0.10
```

Each sub-score is normalised to `0..100`. The final composite is clamped
into the same range and rounded to an integer.

## Sub-scores

### `repo_health` (weight 0.30)

Pulled from the `check_repo_health` analyser, which combines:

| Signal | Source |
|---|---|
| `merge_rate` | % of recent closed PRs that landed (sampled, default 50) |
| `last_commit_date` | `pushed_at` or latest commit in the last 30 days |
| `active_contributors_30d` | Unique commit authors in the last 30 days |
| `has_contributing_guide` | Existence of `CONTRIBUTING.md` (root, `docs/`, or `.github/`) |
| `has_code_of_conduct` | Existence of `CODE_OF_CONDUCT.md` |
| `ci_configured` | Any of `.github/workflows`, CircleCI, Travis, GitLab CI |

These collapse into an `A`-`F` grade, mapped to a numeric sub-score
(`A=95, B=80, C=60, D=40, F=15`). Mapping is intentionally non-linear so an
`F` repo can never bait a top result.

### `issue_freshness` (weight 0.20)

Linear decay from `100` at age ≤ `fresh_issue_days` (14d) to `0` at age ≥
`stale_issue_days` (60d). Age is measured against `updated_at`.

### `issue_clarity` (weight 0.15)

Base score is a function of body length:

- `< clarity_min_body_chars` (80): floor `30`
- `≥ clarity_great_body_chars` (400): `100`
- in between: linear interpolation from `30` → `100`

Bonuses (additive, capped at 100):

- `+5` for fenced code blocks
- `+5` for "steps to reproduce" / "to reproduce"
- `+2.5` for hints / examples / "see ..."

### `merge_friendliness` (weight 0.25)

Direct mapping of `merge_rate`:

- `≥ high_merge_rate` (0.7): `100`
- `≤ low_merge_rate` (0.2): `15`
- in between: linear interpolation

Missing data (no PR sample) defaults to `50` — neither rewarded nor
punished.

### `setup_complexity_inv` (weight 0.10)

A Phase 2 proxy until `get_contribution_guide` ships richer parsing:

```
30 (base)
 + 35 if has_contributing_guide
 + 25 if ci_configured
 + 10 if has_code_of_conduct
```

Capped at `100`.

## Grade mapping

The composite score is bucketed using `grade_cutoffs`:

| Grade | Min score |
|---|---|
| A | 85 |
| B | 70 |
| C | 55 |
| D | 40 |
| F | < 40 |

The grade is surfaced as `health_grade` on `RepoHealth` and as
`repo_health_grade` on every `find_issues` result.

## Repo health grading rules

The repo grader is intentionally separate from the issue scorer, because a
healthy repo can host a stale issue and vice versa. The grader follows a
short rules list (in [`services/repo_analyzer.py`](../src/gfi_scout/services/repo_analyzer.py)):

| Grade | Required |
|---|---|
| A | Last commit ≤ 7d, merge rate ≥ 0.7, `CONTRIBUTING.md` present, CI on |
| B | Last commit ≤ 30d, merge rate ≥ 0.5, `CONTRIBUTING.md` present |
| C | Last commit ≤ 60d, merge rate ≥ 0.2 |
| D | Last commit ≤ stale_repo_commit_days (90d) |
| F | Otherwise |

## Tuning

The weights must sum to `1.0` (±0.01). The loader (`services/scoring_config.py`)
validates this on startup; bad config raises `ScoringConfigError`. Each
field is type-checked.

To experiment with a different ranking, copy `config/scoring_weights.json`,
tweak, then run:

```bash
uv run pytest tests/unit/services/test_issue_scorer.py
```

Add a regression test with a sample issue + expected score so any future
weight changes don't silently shift rankings.
