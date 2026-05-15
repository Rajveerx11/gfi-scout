"""Pre-populate the in-memory cache with popular repos.

Run with: `uv run python scripts/seed_cache.py [language ...]`

Picks a small set of well-known repos per language, fans out `analyse_repo`
calls in parallel, and prints the resulting health grades. Useful for
warming cache during local development so the first `find_issues` call
isn't slow.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gfi_scout.config import load_settings  # noqa: E402
from gfi_scout.services.cache import TTLNamespaceCache  # noqa: E402
from gfi_scout.services.github_api import GitHubClient  # noqa: E402
from gfi_scout.services.repo_analyzer import analyse_repo  # noqa: E402
from gfi_scout.services.scoring_config import get_scoring_config  # noqa: E402

POPULAR = {
    "python": ["django/django", "pallets/flask", "fastapi/fastapi", "pandas-dev/pandas"],
    "typescript": ["microsoft/vscode", "vercel/next.js", "trpc/trpc"],
    "rust": ["rust-lang/rust", "tokio-rs/tokio", "denoland/deno"],
    "go": ["golang/go", "gohugoio/hugo", "kubernetes/kubernetes"],
    "javascript": ["facebook/react", "vuejs/vue", "nodejs/node"],
}


async def seed_for(client: GitHubClient, repo: str) -> str:
    cfg = get_scoring_config()
    health = await analyse_repo(client, repo, cfg=cfg)
    return f"{repo}: grade={health.health_grade} merge_rate={health.merge_rate}"


async def main_async(languages: list[str]) -> int:
    settings = load_settings()
    cache = TTLNamespaceCache(default_ttl_seconds=settings.cache_ttl_minutes * 60)
    async with GitHubClient(token=settings.github_token, cache=cache) as client:
        repos: list[str] = []
        for lang in languages:
            repos.extend(POPULAR.get(lang.lower(), []))
        if not repos:
            print("No repos to seed — pick a known language:", ", ".join(POPULAR))
            return 1

        results = await asyncio.gather(
            *(seed_for(client, r) for r in repos), return_exceptions=True,
        )
        for result in results:
            print(result)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed GFI Scout cache.")
    parser.add_argument(
        "languages", nargs="*", default=["python"],
        help="Languages to seed (default: python).",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args.languages)))


if __name__ == "__main__":
    main()
