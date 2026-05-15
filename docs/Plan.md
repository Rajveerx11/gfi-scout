# 🔍 GFI Scout — Good First Issue MCP Server

> **An MCP server that doesn't just find "good first issues" — it finds issues where beginners actually succeed.**

---

## 🎯 Project Vision

Most "good first issue" finders are glorified search wrappers. GFI Scout is different. It analyzes repository health, maintainer responsiveness, issue freshness, and contribution friendliness — so you stop wasting time on dead issues in abandoned repos.

Built as an MCP (Model Context Protocol) server using Python and FastMCP, it works with **any** MCP-compatible client: Claude Desktop, Cursor, VS Code Copilot, Windsurf, or custom agents.

---

## 📐 Project Structure

> **This project follows strict folder conventions. Every file has a home. No exceptions.**

```
gfi-scout/
│
├── src/
│   └── gfi_scout/                # Main Python package
│       ├── __init__.py
│       │
│       ├── server.py             # MCP server entry point & tool registration
│       ├── config.py             # Server configuration & constants
│       │
│       ├── tools/                # Each MCP tool = one file
│       │   ├── __init__.py
│       │   ├── find_issues.py    # Core issue discovery tool
│       │   ├── check_repo_health.py  # Repository health analysis tool
│       │   ├── check_issue_status.py # Issue freshness & availability tool
│       │   └── get_contrib_guide.py  # Contribution guide summarizer tool
│       │
│       ├── services/             # Business logic & external API wrappers
│       │   ├── __init__.py
│       │   ├── github_api.py     # GitHub REST/GraphQL API client
│       │   ├── repo_analyzer.py  # Repo health scoring engine
│       │   ├── issue_scorer.py   # Issue quality & freshness scoring
│       │   └── cache.py          # Caching layer (rate limit management)
│       │
│       ├── models/               # Pydantic models & data schemas
│       │   ├── __init__.py
│       │   ├── issue.py          # Issue-related models
│       │   ├── repo.py           # Repository-related models
│       │   └── scoring.py        # Scoring result models
│       │
│       └── utils/                # Pure utility/helper functions
│           ├── __init__.py
│           ├── logger.py         # Structured logging
│           ├── rate_limiter.py   # API rate limit handler
│           └── validators.py     # Input validation helpers
│
├── tests/                        # All tests mirror src/ structure
│   ├── __init__.py
│   ├── conftest.py               # Shared fixtures & test config
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── tools/
│   │   ├── services/
│   │   └── utils/
│   ├── integration/
│   │   ├── __init__.py
│   │   └── test_github_api.py
│   └── fixtures/                 # Mock data for tests
│       └── sample_issues.json
│
├── docs/                         # Documentation & project docs
│   ├── ARCHITECTURE.md           # System architecture & design decisions
│   ├── SETUP.md                  # Detailed setup & installation guide
│   ├── TOOLS_REFERENCE.md        # Full MCP tool documentation
│   ├── SCORING_ALGORITHM.md      # How repo health & issue scoring works
│   ├── CONTRIBUTING.md           # Contribution guidelines
│   ├── CHANGELOG.md              # Version history
│   └── assets/                   # Images, diagrams for docs
│       └── architecture.png
│
├── scripts/                      # Automation & dev scripts
│   ├── setup.sh                  # First-time project setup
│   └── seed_cache.py             # Pre-populate cache with popular repos
│
├── config/                       # Configuration files
│   ├── default.json              # Default config values
│   └── scoring_weights.json      # Tunable scoring parameters
│
├── .github/                      # GitHub-specific config
│   ├── workflows/
│   │   ├── ci.yml                # CI pipeline (lint, test, build)
│   │   └── release.yml           # Automated release workflow
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── PULL_REQUEST_TEMPLATE.md
│
├── .env.example                  # Environment variable template
├── .gitignore
├── .python-version               # Python version pin (e.g., 3.12)
├── pyproject.toml                # Project metadata, deps, tool config (single source of truth)
├── uv.lock                       # uv lockfile (committed to repo)
├── LICENSE                       # MIT License
└── README.md                     # Project overview & quick start
```

### Folder Rules (Non-Negotiable)

| Folder | What goes here | What does NOT go here |
|---|---|---|
| `src/gfi_scout/tools/` | One file per MCP tool, only tool definition + handler | Business logic, API calls |
| `src/gfi_scout/services/` | Reusable logic, API clients, scoring engines | Tool definitions, server config |
| `src/gfi_scout/models/` | Pydantic models, enums, type aliases | Runtime logic, API calls |
| `src/gfi_scout/utils/` | Pure functions with no side effects | API calls, stateful logic |
| `docs/` | Markdown docs, architecture diagrams, guides | Code files, configs |
| `config/` | JSON config files, tunable parameters | Secrets, `.env` files |
| `tests/` | Tests only, mirroring `src/` structure | Source code |
| `scripts/` | Dev automation, one-off tasks, setup | Application code |

---

## ⚙️ Tech Stack

| Component | Technology | Reasoning |
|---|---|---|
| Language | Python 3.12+ | Beginner-friendly, rich ecosystem, first-class MCP SDK support |
| MCP SDK | `mcp[cli]` (FastMCP) | Official Python SDK — uses type hints and docstrings to auto-generate tool definitions |
| Package Manager | `uv` | Fast, modern Python package manager recommended by the MCP SDK itself |
| HTTP Client | `httpx` | Async-first, modern HTTP client for GitHub API calls |
| Data Validation | `pydantic` | Type-safe models, auto-serialization, used internally by FastMCP already |
| Caching | In-memory (`cachetools`) → Redis (later) | Start simple, scale when needed |
| Testing | `pytest` + `pytest-asyncio` | Industry standard for Python, great async support |
| Linting | `ruff` | Extremely fast linter + formatter, replaces flake8/black/isort in one tool |
| Type Checking | `mypy` | Catch type errors before runtime |

### Why `uv` Everywhere

`uv` is used for **all** dependency management, virtual environment creation, and script running. No `pip`, no `pip-tools`, no `poetry`. One tool for everything.

```bash
# Creating the project
uv init gfi-scout
cd gfi-scout

# Adding dependencies
uv add "mcp[cli]" httpx pydantic cachetools python-dotenv

# Adding dev dependencies
uv add --dev pytest pytest-asyncio ruff mypy respx

# Running the server
uv run gfi-scout

# Running tests
uv run pytest

# Running linter
uv run ruff check src/

# Running type checker
uv run mypy src/
```

The `uv.lock` file is committed to the repo so every contributor gets identical dependency versions.

---

## 🛠️ MCP Tools Specification

### Tool 1: `find_issues`

> The core tool. Searches for beginner-friendly issues with smart filtering.

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `language` | `str` | Yes | Programming language (e.g., "python", "typescript") |
| `min_stars` | `int` | No | Minimum repo stars (default: 50) |
| `max_stars` | `int` | No | Maximum repo stars (default: 50000) |
| `labels` | `list[str]` | No | Labels to search (default: ["good first issue"]) |
| `max_results` | `int` | No | Results to return (default: 10, max: 25) |
| `sort_by` | `str` | No | "freshness" / "beginner_score" / "repo_health" (default: "beginner_score") |
| `topic` | `str` | No | Topic filter (e.g., "web", "cli", "api", "data-science") |

**Returns:** List of issues, each with:
- Issue title, URL, body preview
- Repository name, stars, language
- `beginner_score` (0–100) — composite score
- `freshness` — how recently the issue was created/updated
- `repo_health` — maintainer activity rating
- Labels and assignee status

**Example FastMCP Implementation Pattern:**

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gfi-scout")

@mcp.tool()
async def find_issues(
    language: str,
    min_stars: int = 50,
    max_stars: int = 50000,
    max_results: int = 10,
    sort_by: str = "beginner_score",
    topic: str | None = None,
) -> list[dict]:
    """Find beginner-friendly open source issues ranked by likelihood of success.

    Searches GitHub for 'good first issue' labeled issues, then scores them
    based on repo health, maintainer responsiveness, and issue freshness.
    """
    # Tool logic here
    ...
```

---

### Tool 2: `check_repo_health`

> Analyzes whether a repo is actually contributor-friendly.

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `repo` | `str` | Yes | Full repo name (e.g., "fastapi/fastapi") |

**Returns:**

| Signal | What it measures |
|---|---|
| `merge_rate` | % of external PRs that get merged |
| `avg_review_time` | Average time from PR open → first review |
| `avg_merge_time` | Average time from PR open → merge |
| `maintainer_response_time` | Avg time to first comment on issues |
| `last_commit_date` | When the repo was last actively committed to |
| `active_contributors_30d` | Unique contributors in last 30 days |
| `has_contributing_guide` | Boolean — does CONTRIBUTING.md exist |
| `has_code_of_conduct` | Boolean |
| `ci_configured` | Boolean — has GitHub Actions / CI pipeline |
| `health_grade` | A / B / C / D / F overall grade |

---

### Tool 3: `check_issue_status`

> Before you start working — is the issue actually available?

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `issue_url` | `str` | Yes | Full GitHub issue URL |

**Returns:**

| Signal | What it measures |
|---|---|
| `is_assigned` | Is someone already assigned? |
| `has_linked_pr` | Is there an open PR for this? |
| `last_activity` | When was the last comment? |
| `is_stale` | No activity for 60+ days? |
| `competitor_prs` | Number of open PRs referencing this issue |
| `maintainer_confirmed` | Has a maintainer commented/confirmed the issue? |
| `availability_verdict` | "AVAILABLE" / "LIKELY_TAKEN" / "STALE" / "RISKY" |

---

### Tool 4: `get_contribution_guide`

> Pulls the info you need to actually start contributing.

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `repo` | `str` | Yes | Full repo name |

**Returns:**
- CONTRIBUTING.md content (summarized)
- Setup instructions
- Testing requirements
- PR conventions (branch naming, commit format)
- Required tools/dependencies
- Estimated setup complexity: "easy" / "moderate" / "complex"

---

## 📊 Scoring Algorithm (High-Level)

### Beginner Score (0–100)

The composite score that ranks issues by how likely a beginner is to succeed.

```
beginner_score = weighted_sum(
    repo_health_score      × 0.30    # Is the repo alive and welcoming?
    issue_freshness_score  × 0.20    # Is the issue recent and relevant?
    issue_clarity_score    × 0.15    # Is the issue well-described?
    merge_friendliness     × 0.25    # Do external PRs actually get merged?
    setup_complexity_inv   × 0.10    # How easy is local setup?
)
```

**Weights are tunable** via `config/scoring_weights.json` — no hardcoded magic numbers.

### Repo Health Grade

| Grade | Criteria |
|---|---|
| **A** | Active daily, merges external PRs within 48hrs, has CONTRIBUTING.md, CI passes |
| **B** | Active weekly, merges within 1 week, has basic docs |
| **C** | Active monthly, some external PRs merged, minimal docs |
| **D** | Sporadic activity, few external PRs merged |
| **F** | No activity in 60+ days, or no external PRs ever merged |

---

## 🚀 Development Phases

### Phase 1 — Foundation (MVP)

**Goal:** A working MCP server with the core `find_issues` tool connected to GitHub.

**Deliverables:**
- [ ] Project scaffolding with `uv init` and full folder structure
- [ ] `pyproject.toml` with all dependencies and tool config (ruff, mypy, pytest)
- [ ] `.python-version` pinned to 3.12
- [ ] MCP server boilerplate using FastMCP (`src/gfi_scout/server.py`)
- [ ] Pydantic models for issues and repos (`src/gfi_scout/models/`)
- [ ] GitHub API client with `httpx` (`src/gfi_scout/services/github_api.py`)
- [ ] `find_issues` tool — basic search with language and label filters
- [ ] Basic rate limiting and error handling
- [ ] Unit tests for core functions
- [ ] README with setup instructions (all commands use `uv`)
- [ ] Working connection with at least one MCP client (Claude Desktop or Cursor)

**Definition of Done:** You can connect GFI Scout to Claude Desktop, type "find me good first issues in Python", and get real, useful results.

---

### Phase 2 — Intelligence Layer

**Goal:** Make results actually smart, not just a search wrapper.

**Deliverables:**
- [ ] `check_repo_health` tool — full repo analysis
- [ ] `check_issue_status` tool — freshness and availability checks
- [ ] Beginner scoring algorithm implementation (`src/gfi_scout/services/issue_scorer.py`)
- [ ] Stale issue detection (linked PRs, last activity, assignment status)
- [ ] Merge rate calculation for repos (external PRs specifically)
- [ ] Caching layer with `cachetools` to avoid GitHub API rate limits
- [ ] `config/scoring_weights.json` — tunable scoring parameters
- [ ] `docs/SCORING_ALGORITHM.md` — document how scoring works
- [ ] Integration tests with mocked GitHub API responses (using `respx`)

**Definition of Done:** Results are ranked by beginner_score. Stale/taken issues are filtered out. Repo health grades are accurate.

---

### Phase 3 — Enrichment & Multi-Platform

**Goal:** Deeper insights and broader platform support.

**Deliverables:**
- [ ] `get_contribution_guide` tool — CONTRIBUTING.md parser + summarizer
- [ ] Setup complexity estimation
- [ ] Topic/domain filtering (web, CLI, data-science, DevOps, etc.)
- [ ] `docs/TOOLS_REFERENCE.md` — full tool documentation
- [ ] End-to-end tests across multiple MCP clients
- [ ] Performance optimization (async parallel API calls with `asyncio.gather`)

**Definition of Done:** Multi-platform issue discovery works. Users get actionable setup info alongside issues.

---

### Phase 4 — Open Source Release & Community

**Goal:** Ship it publicly. Make it contributor-friendly (practice what you preach).

**Deliverables:**
- [ ] `docs/CONTRIBUTING.md` — comprehensive contribution guide
- [ ] GitHub Issue templates (bug report, feature request)
- [ ] PR template
- [ ] CI/CD pipeline (`.github/workflows/ci.yml`) using `uv` for all steps
- [ ] Automated release workflow
- [ ] PyPI package publishing (so users can `uv tool install gfi-scout` or `uvx gfi-scout`)
- [ ] `docs/CHANGELOG.md`
- [ ] Label your own repo's issues as "good first issue" (yes, the irony is intentional)
- [ ] Social launch (README badges, demo GIF, blog post / LinkedIn post)

**Definition of Done:** Anyone can install GFI Scout in under 2 minutes and start finding issues.

---

## 🔐 Configuration & Environment

```env
# .env.example
GITHUB_TOKEN=ghp_xxxxxxxxxxxx    # Required: GitHub Personal Access Token
CACHE_TTL_MINUTES=30             # Optional: Cache duration (default: 30)
LOG_LEVEL=info                   # Optional: debug / info / warn / error
MAX_CONCURRENT_REQUESTS=5        # Optional: Parallel API call limit
```

**GitHub Token Scopes Required:** `public_repo` (read-only access to public repos — no write scopes needed).

---

## 📦 `pyproject.toml` Blueprint

```toml
[project]
name = "gfi-scout"
version = "0.1.0"
description = "MCP server that finds open source issues where beginners actually succeed"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.12"
dependencies = [
    "mcp[cli]>=1.27.0",
    "httpx>=0.28.0",
    "pydantic>=2.10.0",
    "cachetools>=5.5.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
gfi-scout = "gfi_scout.server:main"

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.25.0",
    "ruff>=0.8.0",
    "mypy>=1.14.0",
    "respx>=0.22.0",
]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "ASYNC"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

---

## 🧪 Testing Strategy

| Layer | Tool | What it covers |
|---|---|---|
| Unit | pytest | Scoring logic, data transformers, validators |
| Integration | pytest + respx | GitHub API mocking, full tool execution |
| E2E | Manual + CI | Real MCP client → server → GitHub API round trip |

**Test naming convention:** `test_[module].py` mirroring `src/` structure.

**Coverage target:** 80% on `src/gfi_scout/services/` and `src/gfi_scout/tools/`.

**Running tests:**

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/gfi_scout

# Run specific test file
uv run pytest tests/unit/tools/test_find_issues.py

# Run in verbose mode
uv run pytest -v
```

---

## 📝 Code Quality Rules

1. **No `Any` types** — every variable has a type. Use Pydantic models for structured data.
2. **Every tool returns Pydantic models** — no raw dicts leaving tool boundaries. Serialize at the edge.
3. **Error handling at boundaries** — API calls, user input, and tool handlers must have try-except.
4. **No hardcoded values** — all thresholds go in `config/`. If it might change, it's a config value.
5. **Logging on every API call** — request/response/duration/errors. Use structured logging via `logging`.
6. **Functions do one thing** — if a function has "and" in its description, split it.
7. **Comments explain WHY, not WHAT** — the code shows what; comments explain intent.
8. **All async** — GitHub API calls are async with `httpx.AsyncClient`. No blocking `requests` calls.
9. **Docstrings on every public function** — FastMCP uses these to generate tool descriptions.

---

## 🧭 GitHub API Rate Limit Strategy

| Scenario | Approach |
|---|---|
| Unauthenticated | 60 requests/hour — essentially unusable, enforce token requirement |
| Authenticated | 5,000 requests/hour — workable with caching |
| Single `find_issues` call | ~3–8 API calls (search + repo checks) |
| Heavy usage | Cache repo health data (30 min TTL), cache issue searches (10 min TTL) |
| Rate limit hit | Graceful degradation — return cached data + warning, never crash |

---

## 📄 License

MIT — because the whole point is helping people contribute to open source.

---

## 🏁 Getting Started (For Contributors)

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/gfi-scout.git
cd gfi-scout

# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (creates venv automatically)
uv sync

# Set up environment
cp .env.example .env
# Add your GitHub token to .env

# Run the MCP server
uv run gfi-scout

# Run tests
uv run pytest

# Lint & format
uv run ruff check src/
uv run ruff format src/

# Type check
uv run mypy src/
```

### Connecting to Claude Desktop

Add this to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gfi-scout": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/gfi-scout", "gfi-scout"]
    }
  }
}
```

Then restart Claude Desktop and ask: *"Find me good first issues in Python"*

---

*Built with frustration, then determination. Because finding your first open source contribution shouldn't require a PhD in "how to navigate GitHub."*