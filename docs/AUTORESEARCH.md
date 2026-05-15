# Autoresearch Optimization Loop

GFI Scout Phase 5 adds an evaluation harness for improving the scoring
algorithm with real ground truth. The loop is inspired by an autoresearch
pattern: propose one scoring change, measure it, keep it if the score improves,
revert it if it does not, then repeat.

Do not run the optimization loop until you have used GFI Scout for 2-3 weeks
and labeled real outcomes. The seed data exists only so the infrastructure runs.

## What It Optimizes

The loop optimizes `beginner_score`, the score used by `find_issues` to rank
beginner-friendly GitHub issues. The optimization target is the single `score`
value printed by:

```bash
uv run python eval/evaluate.py
```

The locked files are:

- `eval/evaluate.py`: evaluation logic.
- `eval/ground_truth.json`: human-labeled answer key.

Optimization agents must not edit either file.

## Adding Labeled Issues

Add entries to `eval/ground_truth.json` under the closest matching query. Each
entry needs:

- `issue_url`: full GitHub issue URL.
- `repo`: `owner/repo`.
- `expected_verdict`: `good`, `bad`, or `mediocre`.
- `reason`: short human explanation.
- `labeled_by`: usually `human`.
- `labeled_date`: date in `YYYY-MM-DD` format.

Use `good` when the issue led to, or clearly would lead to, a successful
beginner contribution. Use `bad` for stale, taken, abandoned, hostile, or
misleadingly labeled issues. Use `mediocre` when the issue was possible but the
repo setup, review time, or maintainer process made it rough.

Minimum useful dataset size is 30 labeled issues. Ideally collect 50 or more.

## Manual Session

Run:

```bash
./eval/run_loop.sh 30
```

The script evaluates the baseline, prints the current score, and waits while an
agent makes exactly one change using `eval/research.md`. Press Enter after the
agent commits or reverts. The script evaluates again and appends a row to
`eval/results.tsv`.

## Automated Overnight Loop

Install the optional research dependency:

```bash
uv sync --extra research
```

Set both keys in `.env`:

```bash
GITHUB_TOKEN=...
ANTHROPIC_API_KEY=...
```

Then run:

```bash
uv run python eval/run_loop_auto.py 30
```

The automated runner stops after the first of these limits:

- 30 rounds.
- 10 consecutive non-improvements.
- 3 hours wall clock.

Every kept change is committed separately with the score delta in the commit
message.

## Reading results.tsv

`eval/results.tsv` is generated at runtime and ignored by git.

Columns:

- `round`: optimization round.
- `change_description`: what changed.
- `score_before`: score before the change.
- `score_after`: score after the change.
- `kept`: `yes` if the change improved the score, otherwise `no`.

## FAQ

**How many labeled issues do I need?**

Use at least 30. Prefer 50 or more before trusting the signal.

**How often should I run this?**

Run it after every 20 new ground truth entries, or when you intentionally change
what "good beginner issue" means.
