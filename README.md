<div align="center">

# GFI Scout

**An MCP server and standalone CLI that finds open source issues where beginners actually succeed — not just any issue tagged `good first issue`.**

[![CI](https://github.com/Rajveerx11/gfi-scout/actions/workflows/ci.yml/badge.svg)](https://github.com/Rajveerx11/gfi-scout/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built with uv](https://img.shields.io/badge/built%20with-uv-261230.svg)](https://docs.astral.sh/uv/)
[![MCP](https://img.shields.io/badge/protocol-MCP-7c3aed.svg)](https://modelcontextprotocol.io/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

</div>

---

## Why this exists

Most "good first issue" finders are glorified GitHub search wrappers. They happily hand you issues from abandoned repos, issues already claimed by three other contributors, and issues maintainers will never review.

**GFI Scout ranks results by *likelihood of success*** — repo health, merge rate, maintainer responsiveness, issue freshness, and setup complexity all feed a composite `beginner_score` (0-100). The dead repos sink to the bottom.

It ships as a [Model Context Protocol](https://modelcontextprotocol.io/) server, plus a standalone CLI/TUI for terminal-first workflows.

---

## Features

- 🔎 **`find_issues`** — repo-first language + topic + star-range discovery with scored issue results
- 🩺 **`check_repo_health`** — merge rate, last commit, CONTRIBUTING/CoC/CI probes → A-F grade
- ⏱️ **`check_issue_status`** — assignment, linked PRs, staleness, maintainer confirmation → `AVAILABLE` / `LIKELY_TAKEN` / `STALE` verdict
- 📘 **`get_contribution_guide`** — pulls and summarises `CONTRIBUTING.md`, detects toolchain, estimates setup complexity
- Terminal commands via **`gfi-scout-cli`** and an interactive **`gfi-scout-tui`**
- ⚡ Parallel GitHub API fan-out (`asyncio.gather`) + per-namespace TTL cache for repository search, issue listing, and repo-health probes
- 🎛️ All scoring weights and thresholds live in [`src/gfi_scout/data/scoring_weights.json`](src/gfi_scout/data/scoring_weights.json) — no magic numbers in code
- 🧪 100+ tests (unit + integration), `mypy --strict` clean, `ruff` clean

---

## Requirements

| | |
|---|---|
| Python | **3.12+** |
| Package manager | [`uv`](https://docs.astral.sh/uv/) (all commands go through `uv`) |
| Auth | GitHub Personal Access Token with **`public_repo`** scope (read-only) |

---

## Quick start

```bash
# Clone
git clone https://github.com/Rajveerx11/gfi-scout.git
cd gfi-scout

# Install uv (skip if you have it)
# macOS / Linux:        curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows (PowerShell): irm https://astral.sh/uv/install.ps1 | iex

# Install dependencies (creates .venv automatically)
uv sync

# Configure environment
cp .env.example .env
# edit .env and paste your GitHub token

# Run the MCP server (stdio transport)
uv run gfi-scout

# Or expose a local Streamable HTTP MCP endpoint
uv run gfi-scout --transport streamable-http --host 127.0.0.1 --port 8000

# Or use the standalone CLI/TUI
uv run gfi-scout-cli find python --min-stars 500
uv run gfi-scout-tui
```

### Install as a global `uv` tool

If you only want to run the MCP server / CLI and don't plan to hack on the code, install it once as a global tool. No checkout, no venv to keep around:

```bash
# Install (or update) directly from GitHub
uv tool install --force --from git+https://github.com/Rajveerx11/gfi-scout gfi-scout

# Then the binaries are on $PATH:
gfi-scout                # MCP server (stdio)
gfi-scout-cli find python --min-stars 500
gfi-scout-tui

# Upgrade later:
uv tool install --force --from git+https://github.com/Rajveerx11/gfi-scout gfi-scout
```

You still need a `GITHUB_TOKEN` in the environment (or a `.env` in the directory you run from).

---

## Connecting to an MCP client

### Claude Desktop

Add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gfi-scout": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/gfi-scout", "gfi-scout"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

Restart Claude Desktop, then try:

> *"Find me Python good first issues with at least 500 stars."*
>
> *"Is this issue actually available? https://github.com/fastapi/fastapi/issues/12345"*
>
> *"What's the setup complexity for `pallets/flask`?"*

### Other clients

Cursor, Windsurf, and VS Code Copilot each support MCP servers — point them at the same `uv run` command. Detailed steps in [`docs/SETUP.md`](docs/SETUP.md).

---

## MCP tools

| Tool | What it does |
|---|---|
| [`find_issues`](docs/TOOLS_REFERENCE.md#find_issues) | Repo-first, scored search for beginner-friendly issues |
| [`check_repo_health`](docs/TOOLS_REFERENCE.md#check_repo_health) | A-F grade for a repository's contributor-friendliness |
| [`check_issue_status`](docs/TOOLS_REFERENCE.md#check_issue_status) | Is this specific issue actually available to work on? |
| [`get_contribution_guide`](docs/TOOLS_REFERENCE.md#get_contribution_guide) | Pulls + summarises `CONTRIBUTING.md` / README setup |

See [`docs/TOOLS_REFERENCE.md`](docs/TOOLS_REFERENCE.md) for full parameter and return-shape specs.

---

## CLI and TUI

```bash
uv run gfi-scout-cli find python --min-stars 500 --max-results 10
uv run gfi-scout-cli health fastapi/fastapi
uv run gfi-scout-cli status https://github.com/fastapi/fastapi/issues/12345
uv run gfi-scout-cli guide pallets/flask
uv run gfi-scout-tui
```

Every command supports `--output json` for scripts. See [`docs/CLI.md`](docs/CLI.md).

---

## How scoring works

```
beginner_score = repo_health        × 0.30
               + issue_freshness    × 0.20
               + issue_clarity      × 0.15
               + merge_friendliness × 0.25
               + setup_complexity_inv × 0.10
```

Every weight and threshold is loaded from [`src/gfi_scout/data/scoring_weights.json`](src/gfi_scout/data/scoring_weights.json). Want to retune the ranker? Edit the JSON and re-run — no code changes.

Full breakdown in [`docs/SCORING_ALGORITHM.md`](docs/SCORING_ALGORITHM.md).

---

## Documentation

| Doc | What's in it |
|---|---|
| [`docs/SETUP.md`](docs/SETUP.md) | Step-by-step install, env vars, client wiring |
| [`docs/AGENT_CONNECTIONS.md`](docs/AGENT_CONNECTIONS.md) | Current MCP connection examples for Codex, Claude Code, Cursor, Antigravity, Pi Agent, and Hermes Agent |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Layering rules, request flow, caching, failure model |
| [`docs/CLI.md`](docs/CLI.md) | Standalone CLI and terminal UI usage |
| [`docs/TOOLS_REFERENCE.md`](docs/TOOLS_REFERENCE.md) | Parameters and return schemas for every MCP tool |
| [`docs/SCORING_ALGORITHM.md`](docs/SCORING_ALGORITHM.md) | How `beginner_score` is computed and graded |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to file issues and ship PRs |
| [`SECURITY.md`](SECURITY.md) | Responsible-disclosure policy |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | Release notes |
| [`docs/Plan.md`](docs/Plan.md) | Original spec + phase plan |

---

## Development

```bash
uv sync                              # install everything
uv run pytest                        # 96 tests in ~2 s
uv run ruff check src/ tests/        # lint
uv run ruff format src/ tests/       # format
uv run mypy src/                     # strict type-check
uv run mcp dev src/gfi_scout/server.py  # MCP Inspector
```

`uv.lock` is committed — every contributor gets identical dependency versions.

### Project layout

```
src/gfi_scout/
├── server.py          # FastMCP entry, tool registration
├── cli.py             # Standalone CLI + terminal UI
├── config.py          # Env loading
├── runtime.py         # Shared cache/client wiring
├── tools/             # One file per MCP tool
│   ├── find_issues.py
│   ├── check_repo_health.py
│   ├── check_issue_status.py
│   └── get_contribution_guide.py
├── services/          # GitHub client, scoring, cache
├── models/            # Pydantic models
└── utils/             # Pure helpers (validators, rate limiter, logger)

tests/                 # mirrors src/ layout
docs/                  # markdown docs
scripts/               # dev automation (setup.sh, seed_cache.py)
```

> The scoring config lives inside the package at `src/gfi_scout/data/scoring_weights.json` so it ships with the installed wheel — no separate top-level `config/` directory. (The runtime settings module `gfi_scout/config.py` is unrelated; `data/` holds JSON, `config.py` reads env vars.)

Layer rules and folder contracts: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Troubleshooting

**`scoring config not found: .../Lib/config/scoring_weights.json`**

You're on an old install (≤ v0.1.0) where the scoring config wasn't bundled into the wheel. Fix:

```bash
uv tool install --force --from git+https://github.com/Rajveerx11/gfi-scout gfi-scout
```

If a long-running MCP server process holds the install directory open on Windows (`Access is denied` during reinstall), stop the host (Claude Desktop / Claude Code / Cursor) or kill the `gfi-scout` Python process first, then re-run the command.

**`Missing required environment variable: GITHUB_TOKEN`**

The CLI / MCP server reads `GITHUB_TOKEN` from the environment or a `.env` file in the working directory. For `uv tool` installs, either export it in your shell profile or set it in the MCP client's `env` block (see *Connecting to an MCP client* above).

---

## Contributing

Issues and PRs welcome — practising what we preach. Start at [`CONTRIBUTING.md`](CONTRIBUTING.md). Good first issues are labelled on the [tracker](https://github.com/Rajveerx11/gfi-scout/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Security

Found a security issue? Please **don't** open a public issue — see [`SECURITY.md`](SECURITY.md) for the disclosure process.

GFI Scout only ever needs `public_repo` (read-only) scope on your GitHub token.

---

## License

[MIT](LICENSE) — because the whole point is helping people contribute to open source.

---

<div align="center">

*Built with frustration, then determination. Because finding your first open source contribution shouldn't require a PhD in "how to navigate GitHub."*

</div>
