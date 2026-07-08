# Setup Guide

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (we use it for everything)
- Optional: a GitHub Personal Access Token with `public_repo` scope (60 req/h without one, 5,000 req/h with)

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
| `GITHUB_TOKEN` | — | Optional. PAT with `public_repo` scope; unauthenticated = 60 req/h |
| `CACHE_TTL_MINUTES` | `30` | Default cache TTL |
| `LOG_LEVEL` | `info` | `debug` / `info` / `warn` / `error` |
| `MAX_CONCURRENT_REQUESTS` | `5` | Parallel GitHub call cap |

## Run the server

### Project-local (from the repo root)

```bash
uv run gfi-scout
```

This starts the MCP server on stdio using the project's `.venv`. Use this for
development inside the repo.

### Global (run from anywhere)

Install once as a `uv` tool — the `gfi-scout`, `gfi-scout-cli`, and
`gfi-scout-tui` executables land on your `PATH` and work from any directory:

```bash
uv tool install .
```

Then, from any folder:

```bash
gfi-scout                  # MCP server (stdio)
gfi-scout-cli find python  # CLI
gfi-scout-tui              # interactive TUI
```

Verify the binary location:

```powershell
where.exe gfi-scout   # Windows
which gfi-scout       # macOS / Linux
```

To upgrade after pulling new code:

```bash
uv tool install --force .
```

### Localhost HTTP endpoint

To expose an HTTP MCP endpoint instead of stdio:

```bash
gfi-scout --transport streamable-http --host 127.0.0.1 --port 8000
```

Then connect HTTP-capable MCP clients to:

```text
http://127.0.0.1:8000/mcp
```

### Wire into Claude Code (available in every session, every folder)

After `uv tool install .`, register `gfi-scout` at **user scope** so it auto-launches
inside any Claude Code session, in any directory on your machine:

```powershell
# Windows (PowerShell)
claude mcp add --scope user gfi-scout "C:\Users\<you>\.local\bin\gfi-scout.exe" -e GITHUB_TOKEN=<your_token>
```

```bash
# macOS / Linux
claude mcp add --scope user gfi-scout "$(which gfi-scout)" -e GITHUB_TOKEN=<your_token>
```

Verify:

```bash
claude mcp list           # expect: gfi-scout  ... ✓ Connected
claude mcp get gfi-scout  # expect: Scope: User config (available in all your projects)
```

Inside any Claude Code session, run `/mcp` to see the live status panel. No
manual start command is needed — Claude Code spawns the stdio subprocess on
session launch.

For client-specific setup covering Codex, Claude Code, Cursor, Google
Antigravity, Pi Agent, and Hermes Agent, see
[`AGENT_CONNECTIONS.md`](AGENT_CONNECTIONS.md).

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

### Cursor / Windsurf / VS Code Copilot / other agents

Add an MCP server entry pointing at the same `uv run` command. Each
client's docs cover the exact JSON shape. Current examples for Codex, Claude
Code, Cursor, Google Antigravity, Pi Agent, and Hermes Agent are in
[`AGENT_CONNECTIONS.md`](AGENT_CONNECTIONS.md).

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
| `rate limit exceeded` after a few searches | No `GITHUB_TOKEN` set (60 req/h) — add a token for 5,000 req/h |
| `GitHubAPIError 401` | Token expired or wrong scope |
| `GitHubAPIError 403` with `rate limit` | Cache is empty + you're hammering — wait an hour or wire Redis |
| Server starts but client sees no tools | MCP client config path / command mismatch |
