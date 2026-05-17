# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

GFI Scout — FastMCP server + standalone CLI/TUI that ranks GitHub "good first issues" by likelihood-of-success (repo health, merge rate, issue freshness, setup complexity) instead of raw label search. Python 3.12+, managed exclusively with `uv`.

## Commands

All commands go through `uv` — no `pip`, no `poetry`.

```bash
uv sync                                  # install deps + create .venv
uv run gfi-scout                         # run MCP server (stdio)
uv run gfi-scout-cli find python --min-stars 500
uv run gfi-scout-tui                     # interactive TUI
uv run mcp dev src/gfi_scout/server.py   # MCP Inspector for debugging tools

uv run pytest                            # full suite, coverage gate at 70%
uv run pytest tests/unit/services/test_issue_scorer.py            # single file
uv run pytest tests/unit/services/test_issue_scorer.py::test_name # single test
uv run pytest -k "scorer and not integration"                     # filter
uv run pytest --no-cov                   # skip coverage when iterating

uv run ruff check src/ tests/            # lint
uv run ruff format src/ tests/           # format
uv run mypy src/                         # strict type-check (must pass)
```

All three of `ruff`, `mypy`, `pytest` must pass before any push. `uv.lock` is committed.

Environment: copy `.env.example` → `.env` and set `GITHUB_TOKEN` (PAT with `public_repo` scope, read-only). Missing token raises `ConfigError` at startup.

## Architecture

Strict layered package at `src/gfi_scout/`. Layer rules are non-negotiable — crossing them is a review-blocker.

| Layer | May import | Must NOT import |
|---|---|---|
| `tools/` | `services/`, `models/` | `httpx` directly, business logic |
| `services/` | `httpx`, `models/`, other services | FastMCP, tool surfaces |
| `models/` | Pydantic, stdlib | Anything with side effects |
| `utils/` | stdlib only | I/O, mutable state |

Tool handlers (`tools/find_issues.py`, `check_repo_health.py`, `check_issue_status.py`, `get_contribution_guide.py`) are thin: validate input → fan out to services → return Pydantic model. Heavy logic lives in `services/`.

### Request flow

`server.py` (FastMCP entry, tool registration) → `tools/<tool>.py` (orchestrator) → `services/` (`github_api`, `repo_analyzer`, `issue_scorer`, `scoring_config`, `cache`) → GitHub REST API. The CLI/TUI in `cli.py` calls the same tool handlers directly. Shared cache + `GitHubClient` wiring is in `runtime.py`.

### Parallelism

`find_issues` runs one repository search, fans out per-repo open issue listings, filters assigned issues client-side by default, then fans out one `analyse_repo` call per unique repo when scoring is enabled. Fan-out is capped by `asyncio.Semaphore` (default 5). Each `analyse_repo` runs 7 GitHub calls in parallel via `asyncio.gather`. All I/O is async - no blocking `requests`.

### Caching

`services/cache.py` is a `TTLNamespaceCache` over `cachetools.TTLCache`. `GitHubClient` reads/writes per-namespace before/after each endpoint call. Namespaces: `search_issues` (10m), `search_repositories` (30m), `repo_issues` (5m), `repo` / `repo_pulls` / `repo_contributors` (30m), `issue` / `issue_comments` / `issue_timeline` (5m), `repo_content` (1h). In-memory only; backend swappable via `Cache` protocol.

### Scoring

`beginner_score` (0-100) is computed in `services/issue_scorer.py`:

```
beginner_score = repo_health × 0.30 + issue_freshness × 0.20
               + issue_clarity × 0.15 + merge_friendliness × 0.25
               + setup_complexity_inv × 0.10
```

Every weight and threshold is loaded from `config/scoring_weights.json` via `services/scoring_config.py`. **No magic numbers in code** — retune by editing JSON. Bad config raises `ScoringConfigError` on first scoring call. Changes to scoring behaviour require updating `docs/SCORING_ALGORITHM.md` and a regression test.

### Failure model

- 4xx/5xx from GitHub → `GitHubAPIError` propagated to MCP client.
- 404 on probed content (CONTRIBUTING/CoC/CI) → treated as "not present", does not crash.
- `analyse_repo` failure for one repo → that repo's issues get `health=None`, scoring degrades gracefully.

## Code rules (from `Plan.md` / `CONTRIBUTING.md`)

- No `Any` types. Structured data is a Pydantic model.
- Every MCP tool returns a Pydantic model — never a raw dict.
- Error handling only at boundaries (API calls, user input, tool handlers).
- Every API call is logged: method, url, status, duration.
- Docstrings on every public function — FastMCP exposes them as tool descriptions to the model.
- Functions do one thing. "and" in a docstring means split it.

## Tests

- `tests/` mirrors `src/` exactly. Unit in `tests/unit/`, integration in `tests/integration/`.
- GitHub is mocked via `respx`. The autouse `_block_real_http` fixture **fails the test** if any unmocked call to `api.github.com` is made — never hit the real API from a test.
- Coverage target: 80% on `services/` and `tools/`; suite-wide gate is 70% (`--cov-fail-under=70` in `pyproject.toml`).
- `asyncio_mode = "auto"` — async tests need no decorator.

## Commits

Conventional Commits. Subject ≤ 50 chars. Body explains the *why*. Examples:

```
feat: add topic filter to find_issues
fix(scorer): clamp clarity bonus at 100
```

Update `docs/CHANGELOG.md` under `[Unreleased]` for any user-visible change.

## Layout reference

```
src/gfi_scout/
├── server.py       # FastMCP entry + tool registration
├── cli.py          # CLI + TUI (calls tool handlers directly)
├── runtime.py      # Shared cache / GitHubClient wiring
├── config.py       # Env loading
├── tools/          # One file per MCP tool
├── services/       # github_api, repo_analyzer, issue_scorer, scoring_config, cache
├── models/         # Pydantic
└── utils/          # Pure helpers (validators, rate limiter, logger)

config/             # scoring_weights.json, default.json — tunable, no code change needed
docs/               # All aux markdown lives here (ARCHITECTURE, SCORING_ALGORITHM, CLI, etc.)
eval/               # Offline evaluation harness (ground_truth.json, evaluate.py)
scripts/            # seed_cache.py, smoke_test.py, workflow_demo.py
```

Deeper detail: `docs/ARCHITECTURE.md`, `docs/SCORING_ALGORITHM.md`, `docs/TOOLS_REFERENCE.md`.
