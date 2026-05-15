# MCP Tools Reference

GFI Scout exposes four MCP tools over stdio. Each is a FastMCP-decorated
async function in [`src/gfi_scout/server.py`](../src/gfi_scout/server.py)
delegating to a handler under [`src/gfi_scout/tools/`](../src/gfi_scout/tools/).

---

## `find_issues`

Find beginner-friendly open source issues ranked by likelihood of success.

### Parameters

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `language` | `str` | Yes | — | Programming language (e.g. `"python"`, `"typescript"`) |
| `min_stars` | `int` | No | `50` | Minimum repo stars |
| `max_stars` | `int` | No | `50000` | Maximum repo stars |
| `labels` | `list[str]` | No | `["good first issue"]` | Issue labels to require |
| `max_results` | `int` | No | `10` | Results returned (1-25) |
| `sort_by` | `str` | No | `"beginner_score"` | `"beginner_score"` / `"freshness"` / `"repo_health"` |
| `topic` | `str` | No | — | GitHub topic filter (e.g. `"web"`, `"cli"`) |

### Returns

`list[IssueResult]` — see [`src/gfi_scout/models/issue.py`](../src/gfi_scout/models/issue.py).

Key fields per result:

- `title`, `url`, `body_preview`
- `repo_full_name`, `labels`, `is_assigned`
- `created_at`, `updated_at`
- `beginner_score` (0-100)
- `freshness` (`"fresh"` / `"warm"` / `"stale"`)
- `repo_health_grade` (`"A"` … `"F"`)

### Example

> "Find me good first issues in Python with at least 500 stars."

```json
{
  "language": "python",
  "min_stars": 500,
  "max_results": 10
}
```

---

## `check_repo_health`

Analyse a repository's contributor-friendliness.

### Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `repo` | `str` | Yes | `owner/name` (GitHub URLs accepted) |

### Returns

`RepoHealth` — see [`src/gfi_scout/models/repo.py`](../src/gfi_scout/models/repo.py).

| Field | Description |
|---|---|
| `merge_rate` | % of recent closed PRs merged |
| `avg_review_time_hours` | Approx avg PR review latency |
| `avg_merge_time_hours` | Avg time from PR open → merge |
| `maintainer_response_time_hours` | Avg time to first action on issues |
| `last_commit_date` | Latest commit timestamp |
| `active_contributors_30d` | Unique authors in last 30d |
| `has_contributing_guide` | `CONTRIBUTING.md` present |
| `has_code_of_conduct` | `CODE_OF_CONDUCT.md` present |
| `ci_configured` | CI workflow detected |
| `health_grade` | `A` / `B` / `C` / `D` / `F` |
| `notes` | Human-readable caveats |

---

## `check_issue_status`

Before you start working — is the issue actually available?

### Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `issue_url` | `str` | Yes | Full GitHub issue URL |

### Returns

`IssueStatus` — see [`src/gfi_scout/models/issue.py`](../src/gfi_scout/models/issue.py).

| Field | Description |
|---|---|
| `is_assigned` | Already assigned to someone |
| `has_linked_pr` | A PR references this issue |
| `last_activity` | Most recent comment / update |
| `is_stale` | No activity for `stale_issue_days` (default 60) |
| `competitor_prs` | Count of open PRs referencing this issue |
| `maintainer_confirmed` | A maintainer/owner has commented |
| `availability_verdict` | `"AVAILABLE"` / `"LIKELY_TAKEN"` / `"STALE"` / `"RISKY"` |
| `notes` | Human-readable caveats |

---

## `get_contribution_guide`

Pull `CONTRIBUTING.md` (or README setup section) and summarise it.

### Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `repo` | `str` | Yes | `owner/name` |

### Returns

`ContributionGuide`:

| Field | Description |
|---|---|
| `contributing_summary` | First few paragraphs (cleaned, truncated) |
| `setup_instructions` | Bullet list from setup/install sections |
| `testing_requirements` | Bullet list from testing sections |
| `pr_conventions` | Bullet list on branch/commit/PR rules |
| `required_tools` | Detected toolchain (`node`, `uv`, `docker`, ...) |
| `setup_complexity` | `"easy"` / `"moderate"` / `"complex"` |
| `source_files` | Files actually consulted |

---

## Error handling

All tools raise on:

- Missing `GITHUB_TOKEN` (`ConfigError`)
- Invalid input (`ValidationError`)
- Any non-2xx GitHub response except probed 404s (`GitHubAPIError`)

GitHub rate-limit `403`s propagate as `GitHubAPIError` with `status_code=403`.
Callers should fall back to cached results where possible.
