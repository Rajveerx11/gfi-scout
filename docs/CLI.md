# Standalone CLI and TUI

GFI Scout keeps `gfi-scout` as the MCP server entry point and adds two terminal
entry points:

- `gfi-scout-cli`: command-oriented interface for scripts and shells.
- `gfi-scout-tui`: interactive terminal menu for exploratory use.

Both use the same GitHub client, cache, validators, and scoring code as the MCP
tools.

## Setup

```bash
uv sync
cp .env.example .env
# edit .env and set GITHUB_TOKEN
```

Required environment:

| Key | Description |
|---|---|
| `GITHUB_TOKEN` | GitHub PAT with read-only `public_repo` scope |
| `CACHE_TTL_MINUTES` | Default in-memory cache TTL, default `30` |
| `MAX_CONCURRENT_REQUESTS` | Repo-health fan-out cap, default `5` |
| `LOG_LEVEL` | Python logging level, default `info` |

## Commands

### Find Issues

```bash
uv run gfi-scout-cli find python --min-stars 500 --max-results 10
uv run gfi-scout-cli find typescript --topic cli --label "good first issue,help wanted"
uv run gfi-scout-cli find rust --include-assigned --output json
```

Options:

| Option | Default | Description |
|---|---|---|
| `language` | required | GitHub language qualifier |
| `--min-stars` | `50` | Minimum repo stars |
| `--max-stars` | `50000` | Maximum repo stars |
| `--max-results` | `10` | Result count, clamped by the core tool |
| `--label` | `good first issue` | Comma-separated label list |
| `--topic` | none | GitHub topic filter |
| `--sort-by` | `beginner_score` | `beginner_score`, `freshness`, or `repo_health` |
| `--include-assigned` | false | Include issues with assignees |
| `--no-scoring` | false | Skip repo-health fan-out for faster raw search |
| `--output` | `table` | `table` or `json` |

### Repository Health

```bash
uv run gfi-scout-cli health fastapi/fastapi
uv run gfi-scout-cli health https://github.com/pallets/flask --output json
```

### Issue Status

```bash
uv run gfi-scout-cli status https://github.com/fastapi/fastapi/issues/12345
```

### Contribution Guide

```bash
uv run gfi-scout-cli guide pallets/flask
uv run gfi-scout-cli guide encode/httpx --output json
```

### Interactive TUI

```bash
uv run gfi-scout-cli tui
uv run gfi-scout-tui
```

The TUI prompts for the same inputs as the command interface and renders Rich
tables/panels in the terminal.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Command completed successfully |
| `1` | Invalid input, missing config, or GitHub API failure |
