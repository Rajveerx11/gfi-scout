# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [SemVer](https://semver.org/).

## [Unreleased]

### Added

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
  - `services/gitlab_api.py` — async GitLab client.
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
