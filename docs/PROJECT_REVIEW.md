# GFI Scout — Open Source Project Review

**Date:** 2026-05-15
**Reviewed version:** `0.1.0` (branch `main`)
**Reviewer:** Claude (Opus 4.7)

---

## Verdict: **7.5 / 10**

Solid core. Clean layered architecture, strict mypy, 67 tests, CI matrix, PyPI OIDC release, scoring tunables externalized to JSON. Punches above weight for a `v0.1.0`. Loses points on OSS polish: broken README links, missing Code of Conduct, dead GitLab code path, no coverage gate, bus-factor of 1.

---

## What it does

GFI Scout is a Model Context Protocol (MCP) server that surfaces beginner-friendly open-source issues ranked by **likelihood of success**, not just by the `good first issue` label. It exposes four async MCP tools (`find_issues`, `check_repo_health`, `check_issue_status`, `get_contribution_guide`) built on `FastMCP` over stdio, calling GitHub REST (with partial GitLab support) via `httpx.AsyncClient` using `asyncio.gather` + `Semaphore` for parallel fan-out. A composite `beginner_score` (0–100) blends repo health, freshness, clarity, merge friendliness, and setup complexity.

- **Entry point:** `src/gfi_scout/server.py:126` → `main()`
- **Script:** `pyproject.toml:20` → `gfi-scout`

---

## Score breakdown

| Area          | Score | Notes |
|---------------|-------|-------|
| Architecture  | 9.0   | Layered `services/tools/models/utils`. Docs match code. |
| Code quality  | 8.5   | `mypy --strict`, ruff, Pydantic, type hints solid. Logging sparse. |
| Tests         | 7.5   | 67 tests, `respx` mocks, 1 integration test. No coverage threshold, no badge. |
| CI/CD         | 8.5   | Matrix Py3.12/3.13, OIDC PyPI publish. No Dependabot, no pre-commit. |
| Docs          | 8.0   | 6 docs files + `ARCHITECTURE.md` + `SCORING_ALGORITHM.md`. Broken links in README. |
| OSS hygiene   | 5.5   | CoC missing, `CONTRIBUTING.md` at wrong path, no FUNDING/CITATION, solo author. |
| Product fit   | 8.0   | MCP-server niche, real value, Claude Desktop ready. |

---

## Findings

### Strengths
- `src/`-layout, clean separation: `services/`, `tools/`, `models/`, `utils/`.
- `mypy --strict` enforced in CI (`pyproject.toml:43-47`).
- Ruff with `E,F,I,N,UP,B,SIM,ASYNC` selects; format-check in CI.
- 67 tests across 10 files; `pytest-asyncio` auto mode; `respx` HTTP mocking; JSON fixtures.
- CI matrix on Python 3.12 and 3.13 with `uv sync --frozen`.
- PyPI release via OIDC trusted publishing on `v*.*.*` tags.
- `uv.lock` committed; all top-level deps lower-bounded.
- Scoring weights externalized to `config/scoring_weights.json` — tunable without code change.
- README has 6 badges, quick-start, Claude Desktop config snippet, scoring formula, project layout.
- `SECURITY.md` with supported-versions table and private-disclosure paths.
- `.github/` has issue templates and a thorough PR template.

### Gaps / risks
- **`CODE_OF_CONDUCT.md` missing** despite README link at `README.md:194`. Broken link + missing standard OSS file.
- **`CONTRIBUTING.md` lives at `docs/CONTRIBUTING.md` only.** README links at lines 145 and 192 resolve to a non-existent root file. GitHub repo UI also expects root, `.github/`, or `docs/`.
- **No coverage threshold.** `--cov-report=term-missing` runs but nothing fails CI on regression. No Codecov upload, no badge.
- **No pre-commit hooks.** Lint/format enforced only server-side.
- **Dead GitLab code.** `services/gitlab_api.py` (145 LOC) exists but no MCP tool consumes it.
- **Sparse logging.** Only 11 log call-sites across the codebase; error paths in `github_api.py` raise without context.
- **No `config.yml` for issue templates** to disable blank issues or route security reports.
- **No Dependabot/Renovate config** despite pinned-via-lock dependency model.
- **No `FUNDING.yml`, no `CITATION.cff`** (minor signal).
- **Pre-1.0 (`0.1.0`)** with PyPI publishing wired — no SemVer guarantees for early adopters.
- **Bus-factor 1.** Solo author, very recent history.

---

## Path to 10/10

### P0 — Fix now (trust breakers)

1. **Create `CODE_OF_CONDUCT.md` at root.** Contributor Covenant 2.1. README:194 already links to it.
2. **Move `docs/CONTRIBUTING.md` → root `CONTRIBUTING.md`** (or add a root stub that links to `docs/`). README:145, 192 broken.
3. **Decide on GitLab support.** Either expose `find_issues(platform="gitlab")` in a tool, or delete `services/gitlab_api.py`. 145 LOC of dead code drags maintenance and confuses contributors.
4. **Add coverage threshold.** Set `--cov-fail-under=85` in `pyproject.toml`. Upload to Codecov. Add badge to README.

### P1 — Add next (credibility)

5. **`.github/dependabot.yml`** — weekly updates for `uv` deps and GitHub Actions.
6. **Pre-commit hooks** — ruff + mypy + check-yaml. Stops broken PRs at dev time.
7. **`.github/ISSUE_TEMPLATE/config.yml`** — disable blank issues, route security reports to `SECURITY.md`.
8. **`FUNDING.yml`** + **`CITATION.cff`** — signal maturity.
9. **More logging.** Request IDs, GitHub rate-limit hits, score reasons. 11 sites too thin for ops.
10. **`CHANGELOG.md` at root** (or symlink). Convention is root, not `docs/`.

### P2 — Stretch (10/10 shine)

11. **Bus-factor fix.** Recruit at least one maintainer. Document release process in `CONTRIBUTING.md`. Add `MAINTAINERS.md`.
12. **Benchmarks.** `pytest-benchmark` for the scoring pipeline. Publish numbers in README.
13. **Examples directory.** Real Claude Desktop transcripts, screenshots, GIF in README.
14. **Plugin scoring weights.** Let users point `scoring_weights.json` at a custom path via env var.
15. **v1.0 + SemVer commitment.** Once tool surface is stable, cut 1.0 and add deprecation policy.
16. **GitHub App auth option.** Beyond PATs — higher rate limits.
17. **Observability.** OpenTelemetry span per tool call. MCP ecosystem starting to care.
18. **Docs site.** MkDocs Material on GitHub Pages. 6 markdown files enough to justify.
19. **Conventional Commits enforcement.** Commit-lint action. Recent commits already follow the format.
20. **Release notes automation.** `release-drafter` populates GitHub releases from PR labels.

---

## Quickest 4 commits for biggest jump (7.5 → 9)

1. Add `CODE_OF_CONDUCT.md` + fix `CONTRIBUTING.md` path.
2. Delete `services/gitlab_api.py` (or feature-flag and document it).
3. Coverage gate (`--cov-fail-under=85`) + Codecov badge.
4. `.github/dependabot.yml`.

---

## File references

- `src/gfi_scout/server.py:126` — `main()` entry point
- `pyproject.toml:20` — script declaration
- `pyproject.toml:41` — ruff select list
- `pyproject.toml:43-47` — mypy strict config
- `README.md:145, 192` — broken `CONTRIBUTING.md` links
- `README.md:194` — broken `CODE_OF_CONDUCT.md` link
- `services/gitlab_api.py` — dead 145-LOC module
- `.github/workflows/ci.yml` — CI matrix
- `.github/workflows/release.yml` — OIDC PyPI publish
