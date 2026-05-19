# Architecture

GFI Scout is a FastMCP server that turns a "find me a good first issue"
request into a ranked list of high-signal candidates. This page covers
the why and the moving parts.

## High-level flow

```
MCP client (Claude Desktop / Cursor / Windsurf / ...)
        │
        │  stdio (JSON-RPC)
        ▼
FastMCP server  (src/gfi_scout/server.py)
        │
        ├── find_issues          ┐
        ├── check_repo_health    │  tool handlers in src/gfi_scout/tools/
        ├── check_issue_status   │
        └── get_contribution_guide ┘
                │
                ▼
        services (src/gfi_scout/services/)
        ┌───────────────┐  ┌──────────────────┐  ┌──────────────────┐
        │ github_api    │  │ repo_analyzer    │  │ issue_scorer     │
        │               │  │ scoring_config   │  │ cache            │
        └───────────────┘  └──────────────────┘  └──────────────────┘
                │
                ▼
        GitHub REST API (search / repos / pulls / issues / contents)
```

The standalone CLI/TUI entry point (`src/gfi_scout/cli.py`) calls the same
tool handlers directly. Shared runtime wiring for cache and GitHub client
construction lives in `src/gfi_scout/runtime.py`.

## Layering rules (non-negotiable)

| Layer | Allowed | Forbidden |
|---|---|---|
| `tools/` | Call `services/`, return `models/` | Direct `httpx`, business logic |
| `services/` | `httpx`, `models/`, other services | FastMCP imports, tool surfaces |
| `models/` | Pydantic, stdlib | Side effects |
| `utils/` | Pure functions | I/O, state |

A tool handler is a thin orchestration layer: validate, fan out to services,
serialise to a Pydantic model, return. Anything heavier belongs in
`services/`.

## Caching

[`services/cache.py`](../src/gfi_scout/services/cache.py) provides
`TTLNamespaceCache` — a thin wrapper over `cachetools.TTLCache` with a
bucket per namespace. The `GitHubClient` reads namespace-keyed cache
entries before every endpoint call and writes back on success.

Namespaces and default TTLs:

| Namespace | TTL | Why |
|---|---|---|
| `search_issues` | 10 min | Legacy issue-search client calls churn fast |
| `search_repositories` | 30 min | Candidate repo discovery changes slower than issues |
| `repo` | configured (default 30m) | Repo metadata changes slowly |
| `repo_issues` | 5 min | Open issue availability should stay fresh |
| `repo_pulls` | 30 min | PR sample drives merge_rate |
| `repo_contributors` | 30 min | Contributor list barely changes |
| `issue` / `issue_comments` / `issue_timeline` | 5 min | Issue status must be fresh-ish |
| `repo_content` | 1 hr | CONTRIBUTING / README change rarely |

Cache is in-memory only — a Redis backend can be slotted in later by
implementing the `Cache` protocol.

## Scoring

The composite `beginner_score` is computed in
[`services/issue_scorer.py`](../src/gfi_scout/services/issue_scorer.py).
Every threshold and weight is read from
[`src/gfi_scout/data/scoring_weights.json`](../src/gfi_scout/data/scoring_weights.json) via
[`services/scoring_config.py`](../src/gfi_scout/services/scoring_config.py).
See [SCORING_ALGORITHM.md](SCORING_ALGORITHM.md) for the formula.

## Parallelism

`find_issues` issues one repository search request, then fans out one
open-issue listing call per candidate repo. Assigned issues are filtered
client-side by default. When scoring is enabled, it also fans out one
`analyse_repo` call per unique repo in the result set. Concurrency is capped
by `asyncio.Semaphore` instances (default 5) so we don't accidentally DoS the
GitHub API or our local event loop.

`analyse_repo` itself runs 7 GitHub calls in parallel via
`asyncio.gather` — repo metadata, recent PRs, contributors, recent
commits, CONTRIBUTING / CoC / CI probes.

## Failure model

| Failure | Behaviour |
|---|---|
| Missing `GITHUB_TOKEN` | `ConfigError` on startup |
| 4xx / 5xx from GitHub | `GitHubAPIError` propagated to MCP client |
| 404 on probed content | Treated as "not present", does not crash |
| `analyse_repo` fails for one repo | That repo's issues default to `health=None`, scoring degrades gracefully |
| Bad `scoring_weights.json` | `ScoringConfigError` on first scoring call |

## Why not GraphQL?

The REST API is enough for everything we currently rank on, and it lets
us cache per-endpoint with simple TTLs. A future iteration can collapse
the per-repo fan-out into a single GraphQL query when the bottleneck
becomes obvious — until then, the REST layout maps 1:1 to our model
files and is easier to read.

## Test architecture

- **Unit tests** mock GitHub via `respx`. The autouse `_block_real_http`
  fixture refuses any unmocked outbound call to `api.github.com`, so a
  forgotten mock can never silently hit production.
- **Integration tests** orchestrate the full handler with multiple
  mocked endpoints, exercising the scoring + parallelism logic.
- **No live network tests** in CI — they belong behind a marker that
  only runs locally.
