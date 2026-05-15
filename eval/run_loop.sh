#!/usr/bin/env bash
set -euo pipefail

# Usage: ./eval/run_loop.sh <number_of_rounds>
# Example: ./eval/run_loop.sh 30

ROUNDS="${1:-30}"
RESULTS_FILE="eval/results.tsv"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN is required. Add it to .env or export it before running."
  exit 1
fi

score_from_json() {
  python -c 'import json, sys; print(f"{json.loads(sys.argv[1])[\"score\"]:.4f}")' "$1"
}

is_improved() {
  python -c 'import sys; print("yes" if float(sys.argv[2]) > float(sys.argv[1]) else "no")' "$1" "$2"
}

if [[ ! -f "$RESULTS_FILE" ]]; then
  printf "round\tchange_description\tscore_before\tscore_after\tkept\n" > "$RESULTS_FILE"
fi

baseline_json="$(uv run python eval/evaluate.py | tail -n 1)"
current_score="$(score_from_json "$baseline_json")"

echo "Baseline score: $current_score. Starting optimization loop for $ROUNDS rounds."
echo "Use eval/research.md as the agent prompt. Do not run this loop until ground_truth.json has real labels."

for round in $(seq 1 "$ROUNDS"); do
  echo
  echo "Round $round/$ROUNDS. Current score: $current_score"
  echo "Waiting for agent to make changes... Press Enter after the agent commits or reverts."
  read -r _

  after_json="$(uv run python eval/evaluate.py | tail -n 1)"
  after_score="$(score_from_json "$after_json")"
  kept="$(is_improved "$current_score" "$after_score")"

  printf "%s\t%s\t%s\t%s\t%s\n" \
    "$round" "manual agent round" "$current_score" "$after_score" "$kept" >> "$RESULTS_FILE"

  current_score="$after_score"
  echo "Round $round score: $current_score"
done
