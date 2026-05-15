#!/usr/bin/env bash
# First-time setup for GFI Scout. Idempotent.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Checking for uv"
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found. Install: https://docs.astral.sh/uv/#installation"
    exit 1
fi

echo "==> uv sync"
uv sync

if [[ ! -f .env ]]; then
    echo "==> Creating .env from .env.example"
    cp .env.example .env
    echo
    echo "Edit .env and set GITHUB_TOKEN before running the server."
fi

echo "==> Running unit tests"
uv run pytest -q

echo
echo "Setup complete."
echo "Next: edit .env, then 'uv run gfi-scout'."
