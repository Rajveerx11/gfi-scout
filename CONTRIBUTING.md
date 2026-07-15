# Contributing to GFI Scout

First off — thanks for considering a contribution. The whole point of this
project is to make open source contribution less painful, so we try hard
to make *this* repo welcoming too.

## TL;DR

```bash
git clone https://github.com/Rajveerx11/gfi-scout.git
cd gfi-scout
uv sync
cp .env.example .env  # add your GitHub token
uv run pytest         # everything green?
```

## Before you start

1. Open or comment on the issue you want to take. We label good first
   issues — eat your own dog food.
2. If there's no issue yet, open one describing the change before sinking
   time into a PR. We'll respond quickly.
3. Check `docs/ARCHITECTURE.md` so your change lands in the right layer.

## Local development

Every workflow uses `uv` — no `pip`, no `poetry`.

```bash
# Install deps + create .venv
uv sync

# Run the server
uv run gfi-scout

# Run tests
uv run pytest

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type-check
uv run mypy src/
```

All three must pass before you push.

## Code style

The non-negotiable rules from `Plan.md`:

1. **No `Any` types.** Use Pydantic models for structured data.
2. **Every tool returns a Pydantic model** — never a raw dict.
3. **Error handling at boundaries.** API calls, user input, tool handlers
   must have try/except.
4. **No hardcoded thresholds** — they live in `src/gfi_scout/data/`.
5. **Every API call is logged** with method/url/status/duration.
6. **Functions do one thing.** If you write "and" in the docstring, split it.
7. **Comments explain WHY, not WHAT.**
8. **All I/O is async.** No blocking `requests`.
9. **Docstrings on every public function** — FastMCP uses them for tool
   descriptions visible to the model.

## Folder rules

| Folder | What goes here |
|---|---|
| `src/gfi_scout/tools/` | One file per MCP tool — handler + validation only |
| `src/gfi_scout/services/` | Business logic, API clients, scoring |
| `src/gfi_scout/models/` | Pydantic models, type aliases |
| `src/gfi_scout/utils/` | Pure helpers |
| `tests/` | Mirrors `src/` exactly |
| `docs/` | Markdown only |
| `src/gfi_scout/data/` | Tunable JSON configs (bundled in the package) |
| `scripts/` | Dev automation |

If your change crosses a layer, open an issue first so we can talk about
it before you write the code.

## Commits

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add topic filter to find_issues
fix(scorer): clamp clarity bonus at 100
docs: clarify scoring weight sum invariant
test: cover stale issue edge case
chore: bump ruff to 0.15
```

Subject line ≤ 50 chars. Body explains the *why*.

## Pull requests

- One logical change per PR. Smaller is better.
- Link the issue you're closing: `Closes #123`.
- CI must pass (`ruff`, `mypy`, `pytest`).
- Update `docs/CHANGELOG.md` under `[Unreleased]`.
- If you change scoring behaviour, update
  `docs/SCORING_ALGORITHM.md` and add a regression test.

## Tests

- Unit tests live in `tests/unit/` mirroring `src/`.
- Integration tests live in `tests/integration/` and use `respx` to mock
  GitHub. **Never** hit the real GitHub API from a test — the autouse
  `_block_real_http` fixture will fail the test if you do.
- Coverage target: 80% on `services/` and `tools/`.

## Releases

Maintainers cut releases by tagging `vX.Y.Z` on `main`. The `release.yml`
workflow builds and publishes to PyPI. The `CHANGELOG.md` entry under
`[Unreleased]` graduates to a versioned section.

## Code of conduct

Be kind. Assume good faith. If you wouldn't say it in an issue review on
your day job, don't say it here.
