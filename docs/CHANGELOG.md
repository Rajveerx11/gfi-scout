# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [SemVer](https://semver.org/).

## [Unreleased]

### Added

- Documented global install via `uv tool install .` and user-scope Claude Code
  registration (`claude mcp add --scope user`) so the MCP server is available
  in every Claude Code session, in any directory. See `SETUP.md` and
  `AGENT_CONNECTIONS.md`.
- `find_issues` now uses a repo-first discovery flow: search repositories by
  language/topic/star range, list matching open issues per repo, then score and
  rank results. This avoids GitHub issue-search queries that incorrectly put
  `stars:` on issue results.
- GitHub client helpers for repository search and per-repository issue listing,
  with dedicated cache namespaces.
- Standalone `gfi-scout-cli` command suite for issue search, repo health,
  issue status, and contribution-guide inspection.
- Interactive `gfi-scout-tui` terminal menu backed by the same tool handlers.
- Shared runtime wiring for MCP and CLI entry points.
- **Phase 2** — Intelligence Layer
  - `check_repo_health` tool: merge rate, last commit, contributor count,
    CONTRIBUTING / CoC / CI probes → `A`-`F` grade.
  - `check_issue_status` tool: assignment, linked PRs, staleness,
    competitor PRs, maintainer confirmation → availability verdict.
  - `issue_scorer` + `repo_analyzer` services with tunable weights in
    `config/scoring_weights.json`.
  - `TTLNamespaceCache` (`cachetools.TTLCache` per namespace).
  - `find_issues` now computes `beginner_score`, `freshness`, and
    `repo_health_grade` per result; respects `sort_by`.
  - Parallel repo-health fan-out via `asyncio.gather` + `Semaphore`.
  - Integration tests covering the full handler with mocked GitHub.
  - `docs/SCORING_ALGORITHM.md`.
- **Phase 3** — Enrichment & Multi-Platform
  - `get_contribution_guide` tool: pulls + summarises `CONTRIBUTING.md`
    (or README setup section), detects required toolchain, estimates
    `easy` / `moderate` / `complex` setup.
  - `utils/rate_limiter.py` — async token-bucket limiter.
  - `docs/TOOLS_REFERENCE.md`, `docs/ARCHITECTURE.md`, `docs/SETUP.md`.
- **Phase 4** — Open Source Release plumbing
  - `docs/CONTRIBUTING.md`.
  - GitHub issue + PR templates under `.github/`.
  - `.github/workflows/ci.yml` (lint + type + test) and `release.yml`
    (PyPI publish on tag).
  - `scripts/setup.sh`, `scripts/seed_cache.py`.

## [0.1.0] — Phase 1 — Foundation

### Added

- FastMCP scaffold, `find_issues` MVP, GitHub Search client, Pydantic
  models, structured logging, unit tests.
