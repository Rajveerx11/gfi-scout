# Setup Guide

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (we use it for everything)
- A GitHub Personal Access Token with `public_repo` scope

## Install

```bash
git clone https://github.com/Rajveerx11/gfi-scout.git
cd gfi-scout

# Install uv (Unix / macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install uv (Windows PowerShell)
# irm https://astral.sh/uv/install.ps1 | iex

# Sync deps (creates .venv automatically)
uv sync
```

## Configure

```bash
cp .env.example .env
# edit .env, paste your GitHub token
```

`.env` keys:

| Key | Default | Description |
|---|---|---|
| `GITHUB_TOKEN` | — | **Required.** PAT with `public_repo` scope |
| `CACHE_TTL_MINUTES` | `30` | Default cache TTL |
| `LOG_LEVEL` | `info` | `debug` / `info` / `warn` / `error` |
| `MAX_CONCURRENT_REQUESTS` | `5` | Parallel GitHub call cap |

## Run the server

```bash
uv run gfi-scout
```

This starts the MCP server on stdio. Wire it to a client below.

## Run the CLI or TUI

```bash
uv run gfi-scout-cli find python --min-stars 500
uv run gfi-scout-cli health fastapi/fastapi
uv run gfi-scout-tui
```

The CLI supports table output by default and `--output json` for scripts.
See [`CLI.md`](CLI.md) for the full command reference.

## Wiring clients

### Claude Desktop

Edit `claude_desktop_config.json` (location depends on OS):

```json
{
  "mcpServers": {
    "gfi-scout": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/gfi-scout", "gfi-scout"]
    }
  }
}
```

Restart Claude Desktop. Ask: *"Find me good first issues in Python."*

### Cursor / Windsurf / VS Code Copilot

Add an MCP server entry pointing at the same `uv run` command. Each
client's docs cover the exact JSON shape.

## Verify

```bash
# Lint
uv run ruff check src/ tests/

# Type-check
uv run mypy src/

# Tests
uv run pytest
```

If all three pass, you're set.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ConfigError: Missing required environment variable: GITHUB_TOKEN` | `.env` missing or malformed |
| `GitHubAPIError 401` | Token expired or wrong scope |
| `GitHubAPIError 403` with `rate limit` | Cache is empty + you're hammering — wait an hour or wire Redis |
| Server starts but client sees no tools | MCP client config path / command mismatch |
