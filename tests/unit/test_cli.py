from __future__ import annotations

import json
from typing import Any

import httpx
import respx

from gfi_scout.cli import build_parser, main


def test_parser_accepts_find_options() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "find",
            "python",
            "--label",
            "good first issue,help wanted",
            "--topic",
            "cli",
            "--include-assigned",
            "--no-scoring",
            "--output",
            "json",
        ]
    )

    assert args.command == "find"
    assert args.language == "python"
    assert args.labels == "good first issue,help wanted"
    assert args.topic == "cli"
    assert args.include_assigned is True
    assert args.no_scoring is True
    assert args.output == "json"


def test_find_command_outputs_json(
    monkeypatch: Any,
    respx_mock: respx.MockRouter,
    sample_issues: dict[str, Any],
    capsys: Any,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    route = respx_mock.get("/search/issues").mock(
        return_value=httpx.Response(200, json=sample_issues)
    )

    exit_code = main(["find", "python", "--no-scoring", "--output", "json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["repo_full_name"] == "acme/widgets"
    assert payload[0]["title"] == "Add type hints to utils module"
    request = route.calls.last.request
    assert request.url.params.get("per_page") == "10"
    assert "language:python" in (request.url.params.get("q") or "")


def test_missing_token_returns_nonzero(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    exit_code = main(["find", "python", "--no-scoring", "--output", "json"])

    assert exit_code == 1
    assert "Missing required environment variable: GITHUB_TOKEN" in capsys.readouterr().err
