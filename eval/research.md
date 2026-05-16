# GFI Scout Autoresearch Instructions

You are optimizing GFI Scout's `beginner_score` formula. The score ranks GitHub
issues by how likely they are to become successful beginner contributions.

Your objective is simple: maximize the single `score` value printed by:

```bash
uv run python eval/evaluate.py
```

The last line of stdout is the only optimization target.

## Files You May Modify

- `config/scoring_weights.json`: change weight values. The weights must sum to 1.0.
- `src/gfi_scout/services/issue_scorer.py`: refactor scoring logic, add signals, or change thresholds.
- `src/gfi_scout/services/`: add helper functions only if they are necessary.
- `src/gfi_scout/models/scoring.py`: add fields only if new scoring signals need them.

## Files You Must Never Modify

- `eval/evaluate.py`: locked evaluation script.
- `eval/ground_truth.json`: locked human-labeled answer key.
- `src/gfi_scout/services/github_api.py`: stable API client.
- `src/gfi_scout/tools/find_issues.py`: owns sort/filter logic the evaluator
  relies on (`sort_by`, `unassigned_only`, label/topic validation). Editing it
  would change ranking outside the scoring formula and game the evaluator.
- `tests/`: do not modify existing tests.

If you modify the locked files, the run is invalid. The evaluation must stay
honest.

## Research Directions

- Adjust weight ratios in `scoring_weights.json`.
- Change the stale issue threshold. Current baseline is 60 days; try 30, 45, or 90.
- Add a signal for repositories that merged an external PR in the last 14 days.
- Add a signal for issues with fewer than 3 comments.
- Add a signal for repositories with fewer than 5000 stars.
- Penalize repositories where average PR review time exceeds 7 days.
- Boost issues created in the last 7 days.
- Penalize issues that have any linked PR, including draft PRs.
- Try non-linear scoring, such as log scale for star count instead of linear scale.

## Rules Per Round

1. Make one change per round. Do not stack multiple ideas.
2. Keep the change under 50 changed lines.
3. Run `uv run python eval/evaluate.py`.
4. If the score improves, commit the change:

```bash
git add . && git commit -m "research: <what you changed> (score: X.XX -> Y.YY)"
```

5. If the score stays the same or gets worse, revert:

```bash
git checkout -- config/ src/gfi_scout/services/issue_scorer.py
```

6. Keep a running log in `eval/results.tsv`. This file is gitignored and must not be committed.
7. If a change improves score but adds more than 50 lines of complexity, revert it.
8. Stop after 30 rounds, or after 10 consecutive rounds without improvement.

## results.tsv Format

```tsv
round	change_description	score_before	score_after	kept
1	increased merge_friendliness weight to 0.40	0.42	0.55	yes
2	added 14-day external PR signal	0.55	0.61	yes
3	reduced stale threshold to 30 days	0.61	0.58	no
```

## Measurement Notes

The evaluator calls the real `find_issues` flow using GitHub API data. It checks
whether human-labeled good issues appear in the top 10 and whether bad issues
are kept out of those positions. Closed or missing issues may naturally be
absent from live search results; do not change the evaluator to make that easier.
