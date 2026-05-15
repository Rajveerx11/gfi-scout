"""Fully automated autoresearch loop using the Anthropic API.

This runner is intentionally separate from evaluate.py. It may edit and commit
the scoring implementation, while evaluate.py and ground_truth.json stay locked.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, TypedDict, cast

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_PATH = ROOT / "eval" / "research.md"
RESULTS_PATH = ROOT / "eval" / "results.tsv"
CONFIG_PATH = ROOT / "config" / "scoring_weights.json"
SCORER_PATH = ROOT / "src" / "gfi_scout" / "services" / "issue_scorer.py"

DEFAULT_MAX_ROUNDS = 30
MAX_NON_IMPROVEMENTS = 10
MAX_WALL_SECONDS = 3 * 60 * 60
EVAL_TIMEOUT_SECONDS = 330
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")


class EvalPayload(TypedDict):
    score: float


def run_command(
    args: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=check,
    )


def evaluate() -> float:
    result = run_command(
        ["uv", "run", "python", "eval/evaluate.py"],
        timeout=EVAL_TIMEOUT_SECONDS,
    )
    last_line = result.stdout.strip().splitlines()[-1]
    payload = cast(EvalPayload, json.loads(last_line))
    return float(payload["score"])


def ensure_results_file() -> None:
    if not RESULTS_PATH.exists():
        RESULTS_PATH.write_text(
            "round\tchange_description\tscore_before\tscore_after\tkept\n",
            encoding="utf-8",
        )


def append_result(
    round_number: int,
    description: str,
    before: float,
    after: float,
    kept: bool,
) -> None:
    with RESULTS_PATH.open("a", encoding="utf-8") as fp:
        fp.write(
            f"{round_number}\t{description}\t{before:.4f}\t{after:.4f}\t"
            f"{'yes' if kept else 'no'}\n"
        )


def anthropic_client(api_key: str) -> Any:
    anthropic = importlib.import_module("anthropic")
    return anthropic.Anthropic(api_key=api_key)


def _response_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []):
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts).strip()


def extract_diff(text: str) -> str:
    fenced = re.search(r"```(?:diff|patch)?\s*(.*?)```", text, re.DOTALL)
    candidate = fenced.group(1).strip() if fenced else text.strip()
    if "*** Begin Patch" in candidate:
        raise ValueError("Expected a unified diff for git apply, not an apply_patch block")
    if "diff --git " not in candidate:
        raise ValueError("Response did not contain a git unified diff")
    return candidate + "\n"


def propose_change(client: Any, current_score: float, round_number: int) -> tuple[str, str]:
    research = RESEARCH_PATH.read_text(encoding="utf-8")
    scoring_config = CONFIG_PATH.read_text(encoding="utf-8")
    issue_scorer = SCORER_PATH.read_text(encoding="utf-8")
    user_message = f"""
Current evaluation score: {current_score:.4f}
Round: {round_number}

Return exactly one small change as a git unified diff. Touch only:
- config/scoring_weights.json
- src/gfi_scout/services/issue_scorer.py

Keep the diff under 50 changed lines. Include a one-line description before
the diff in the form: CHANGE: <description>

config/scoring_weights.json:
```json
{scoring_config}
```

src/gfi_scout/services/issue_scorer.py:
```python
{issue_scorer}
```
""".strip()

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=research,
        messages=[{"role": "user", "content": user_message}],
    )
    text = _response_text(response)
    first_line = text.splitlines()[0] if text else "CHANGE: automated scoring change"
    description = first_line.removeprefix("CHANGE:").strip() or "automated scoring change"
    return description, extract_diff(text)


def changed_line_count() -> int:
    result = run_command(["git", "diff", "--numstat"], check=False)
    total = 0
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added, deleted = parts[0], parts[1]
        if added.isdigit():
            total += int(added)
        if deleted.isdigit():
            total += int(deleted)
    return total


def apply_diff(diff: str) -> None:
    run_command(["git", "apply", "--check", "-"], input_text=diff)
    run_command(["git", "apply", "-"], input_text=diff)


def revert_modifiable_files() -> None:
    run_command(
        [
            "git",
            "checkout",
            "--",
            "config/scoring_weights.json",
            "src/gfi_scout/services/issue_scorer.py",
        ],
        check=False,
    )


def commit_change(description: str, before: float, after: float) -> None:
    run_command(
        ["git", "add", "config/scoring_weights.json", "src/gfi_scout/services/issue_scorer.py"]
    )
    message = f"research: {description} (score: {before:.4f} -> {after:.4f})"
    run_command(["git", "commit", "-m", message])


def parse_rounds(argv: list[str]) -> int:
    if len(argv) < 2:
        return DEFAULT_MAX_ROUNDS
    return min(int(argv[1]), DEFAULT_MAX_ROUNDS)


def main(argv: list[str]) -> int:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY is required for eval/run_loop_auto.py", file=sys.stderr)
        return 1
    if not os.getenv("GITHUB_TOKEN"):
        print("GITHUB_TOKEN is required for eval/run_loop_auto.py", file=sys.stderr)
        return 1

    max_rounds = parse_rounds(argv)
    ensure_results_file()
    client = anthropic_client(api_key)
    start = time.monotonic()
    non_improvements = 0
    current_score = evaluate()
    print(f"Baseline score: {current_score:.4f}. Starting automated loop for {max_rounds} rounds.")

    for round_number in range(1, max_rounds + 1):
        if non_improvements >= MAX_NON_IMPROVEMENTS:
            print("Stopping after 10 consecutive non-improvements.")
            break
        if time.monotonic() - start >= MAX_WALL_SECONDS:
            print("Stopping after 3 hours wall clock.")
            break

        description, diff = propose_change(client, current_score, round_number)
        try:
            apply_diff(diff)
            if changed_line_count() > 50:
                raise ValueError("Diff changed more than 50 lines")
            after_score = evaluate()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
            print(f"Round {round_number} failed: {exc}")
            revert_modifiable_files()
            append_result(round_number, description, current_score, current_score, False)
            non_improvements += 1
            continue

        improved = after_score > current_score
        append_result(round_number, description, current_score, after_score, improved)
        if improved:
            commit_change(description, current_score, after_score)
            print(f"Round {round_number} kept: {current_score:.4f} -> {after_score:.4f}")
            current_score = after_score
            non_improvements = 0
        else:
            revert_modifiable_files()
            print(f"Round {round_number} reverted: {current_score:.4f} -> {after_score:.4f}")
            non_improvements += 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
