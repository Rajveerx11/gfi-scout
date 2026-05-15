# GFI Scout

> MCP server that finds open source issues where beginners actually succeed — not just any issue labeled "good first issue".

GFI Scout analyzes repository health, maintainer responsiveness, and issue freshness so you stop wasting time on dead issues in abandoned repos. Built on FastMCP (Python), so it works with any MCP-compatible client: Claude Desktop, Cursor, VS Code Copilot, Windsurf, or custom agents.

**Status:** Phase 1 MVP — the `find_issues` tool is live; smart scoring and multi-platform support land in later phases. See `Plan.md` for the full roadmap.

---

## Requirements

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/) (all dependency, venv, and script commands go through `uv`)
- A GitHub Personal Access Token with **`public_repo`** scope (read-only is enough)

---

## Quick start

```bash
# Clone
git clone https://github.com/Rajveerx11/gfi-scout.git
cd gfi-scout

# Install uv (skip if you already have it)
# Windows (PowerShell): irm https://astral.sh/uv/install.ps1 | iex
# macOS / Linux:         curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (creates .venv automatically)
uv sync

# Configure environment
cp .env.example .env
# then edit .env and paste your GitHub token

# Run the MCP server (stdio transport)
uv run gfi-scout
```

---

## Available tools (Phase 1)

| Tool | Purpose |
|---|---|
| `find_issues` | Search GitHub for beginner-friendly issues filtered by language, star range, labels, and topic. Returns title, URL, body preview, repo, labels, and assignment status. |

Future phases will add `check_repo_health`, `check_issue_status`, and `get_contribution_guide` (see `Plan.md`).

---

## Connecting to Claude Desktop

Add this to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gfi-scout": {
      "command": "uv",
      "args": ["run", "--directory", "C:/gfi-scout", "gfi-scout"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

Restart Claude Desktop, then ask: *"Find me good first issues in Python."*

---

## Development

```bash
# Lint and format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type-check
uv run mypy src/

# Run tests
uv run pytest

# Open the MCP Inspector for local debugging
uv run mcp dev src/gfi_scout/server.py
```

The `uv.lock` file is committed so every contributor gets identical dependency versions.

---

## Project structure

```
src/gfi_scout/
├── server.py         # FastMCP server + tool registration
├── config.py         # Env loading & constants
├── tools/            # One file per MCP tool
├── services/         # GitHub client, cache stub, scoring (later)
├── models/           # Pydantic models
└── utils/            # Pure helpers
tests/                # pytest mirrors src/ layout
```

See `Plan.md` for the full specification, folder rules, and phase breakdown.

---

## License

MIT — because the whole point is helping people contribute to open source.
