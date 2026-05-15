"""Locked scoring evaluation for GFI Scout autoresearch.

This file is intentionally treated as read-only by optimization agents. It
loads human-labeled ground truth, calls the real `find_issues` pipeline, and
prints one JSON line with the optimization score as the last line on stdout.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict, cast

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gfi_scout.config import ConfigError, load_settings  # noqa: E402
from gfi_scout.services.cache import TTLNamespaceCache  # noqa: E402
from gfi_scout.services.github_api import GitHubAPIError, GitHubClient  # noqa: E402
from gfi_scout.services.scoring_config import get_scoring_config  # noqa: E402
from gfi_scout.tools.find_issues import find_issues  # noqa: E402

GROUND_TRUTH_PATH = ROOT / "eval" / "ground_truth.json"
EVAL_TIMEOUT_SECONDS = 300
MAX_RESULTS = 25
TOP_K = 10

Verdict = Literal["good", "bad", "mediocre"]


class OutputPayload(TypedDict):
    score: float
    total_queries: int
    avg_precision_at_10: float
    good_in_top10: int
    bad_in_top10: int
    timestamp: str


@dataclass(frozen=True)
class LabeledIssue:
    issue_url: str
    repo: str
    expected_verdict: Verdict


@dataclass(frozen=True)
class GroundTruthQuery:
    query_id: str
    language: str
    min_stars: int
    max_stars: int
    labeled_issues: list[LabeledIssue]


def _json_line(payload: OutputPayload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalise_url(value: object) -> str:
    return str(value).rstrip("/")


def _require_dict(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return cast(dict[str, object], value)


def _require_str(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} must be a non-empty string")
    return value


def _require_int(value: object, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{context} must be an integer")
    return value


def _parse_verdict(value: object, context: str) -> Verdict:
    verdict = _require_str(value, context)
    if verdict not in {"good", "bad", "mediocre"}:
        raise ValueError(f"{context} must be good, bad, or mediocre")
    return cast(Verdict, verdict)


def load_ground_truth(path: Path = GROUND_TRUTH_PATH) -> list[GroundTruthQuery]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    data = _require_dict(raw, "ground truth root")
    raw_queries = data.get("queries")
    if not isinstance(raw_queries, list):
        raise ValueError("ground truth queries must be a list")

    queries: list[GroundTruthQuery] = []
    for query_index, raw_query in enumerate(raw_queries):
        query = _require_dict(raw_query, f"queries[{query_index}]")
        raw_issues = query.get("labeled_issues")
        if not isinstance(raw_issues, list):
            raise ValueError(f"queries[{query_index}].labeled_issues must be a list")

        labeled_issues: list[LabeledIssue] = []
        for issue_index, raw_issue in enumerate(raw_issues):
            context = f"queries[{query_index}].labeled_issues[{issue_index}]"
            issue = _require_dict(raw_issue, context)
            labeled_issues.append(
                LabeledIssue(
                    issue_url=_normalise_url(
                        _require_str(issue.get("issue_url"), "labeled issue_url")
                    ),
                    repo=_require_str(issue.get("repo"), "labeled repo"),
                    expected_verdict=_parse_verdict(
                        issue.get("expected_verdict"),
                        "labeled expected_verdict",
                    ),
                )
            )

        queries.append(
            GroundTruthQuery(
                query_id=_require_str(query.get("query_id"), "query_id"),
                language=_require_str(query.get("language"), "language"),
                min_stars=_require_int(query.get("min_stars"), "min_stars"),
                max_stars=_require_int(query.get("max_stars"), "max_stars"),
                labeled_issues=labeled_issues,
            )
        )
    return queries


def _empty_payload(total_queries: int) -> OutputPayload:
    return {
        "score": 0.0,
        "total_queries": total_queries,
        "avg_precision_at_10": 0.0,
        "good_in_top10": 0,
        "bad_in_top10": 0,
        "timestamp": _timestamp(),
    }


async def _evaluate() -> OutputPayload:
    queries = load_ground_truth()
    if not queries:
        return _empty_payload(0)

    try:
        settings = load_settings()
    except ConfigError:
        return _empty_payload(len(queries))

    cache = TTLNamespaceCache(default_ttl_seconds=settings.cache_ttl_minutes * 60)
    cfg = get_scoring_config()

    precision_sum = 0.0
    good_in_top10 = 0
    bad_in_top10 = 0
    evaluated_queries = 0

    async with GitHubClient(token=settings.github_token, cache=cache) as client:
        for query in queries:
            label_by_url = {
                _normalise_url(issue.issue_url): issue.expected_verdict
                for issue in query.labeled_issues
            }
            try:
                results = await find_issues(
                    client,
                    language=query.language,
                    cfg=cfg,
                    min_stars=query.min_stars,
                    max_stars=query.max_stars,
                    max_results=MAX_RESULTS,
                    sort_by="beginner_score",
                )
            except GitHubAPIError:
                continue

            top_results = results[:TOP_K]
            if not top_results:
                evaluated_queries += 1
                continue

            query_good = 0
            for result in top_results:
                verdict = label_by_url.get(_normalise_url(result.url))
                if verdict == "good":
                    query_good += 1
                    good_in_top10 += 1
                elif verdict == "bad":
                    bad_in_top10 += 1
            precision_sum += query_good / min(TOP_K, len(top_results))
            evaluated_queries += 1

    avg_precision = precision_sum / evaluated_queries if evaluated_queries else 0.0
    score = round(avg_precision, 4)
    return {
        "score": score,
        "total_queries": len(queries),
        "avg_precision_at_10": score,
        "good_in_top10": good_in_top10,
        "bad_in_top10": bad_in_top10,
        "timestamp": _timestamp(),
    }


async def _main() -> OutputPayload:
    try:
        return await asyncio.wait_for(_evaluate(), timeout=EVAL_TIMEOUT_SECONDS)
    except TimeoutError:
        total_queries = len(load_ground_truth())
        return _empty_payload(total_queries)


if __name__ == "__main__":
    print(_json_line(asyncio.run(_main())))
