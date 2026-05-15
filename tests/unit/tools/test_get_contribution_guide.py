from __future__ import annotations

import base64

import httpx
import pytest
import respx

from gfi_scout.services.github_api import GitHubClient
from gfi_scout.tools.get_contribution_guide import get_contribution_guide

SAMPLE_CONTRIBUTING = """\
# Contributing

Welcome.

## Installation

- Install Node 20+
- Run `npm install`
- Copy `.env.example` to `.env`

## Testing

- Run `npm test`
- Add tests under `tests/`

## Pull Requests

- Branch from `main`
- Use Conventional Commits

We use Docker for local development.
"""


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


@pytest.mark.asyncio
async def test_parses_contributing_md(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    repo = "acme/widgets"
    respx_mock.get(f"/repos/{repo}/contents/CONTRIBUTING.md").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "CONTRIBUTING.md",
                "encoding": "base64",
                "content": _b64(SAMPLE_CONTRIBUTING),
            },
        )
    )
    # README probe
    respx_mock.get(f"/repos/{repo}/contents/README.md").mock(return_value=httpx.Response(404))
    respx_mock.get(f"/repos/{repo}/contents/readme.md").mock(return_value=httpx.Response(404))
    respx_mock.get(f"/repos/{repo}/contents/Readme.md").mock(return_value=httpx.Response(404))
    respx_mock.get(f"/repos/{repo}/contents/README.rst").mock(return_value=httpx.Response(404))

    guide = await get_contribution_guide(github_client, repo)

    assert guide.repo_full_name == repo
    assert any("npm install" in step for step in guide.setup_instructions)
    assert any("npm test" in step for step in guide.testing_requirements)
    assert any("Conventional Commits" in c for c in guide.pr_conventions)
    assert "node" in guide.required_tools
    assert "npm" in guide.required_tools
    assert "docker" in guide.required_tools
    assert guide.setup_complexity == "moderate"
    assert "CONTRIBUTING.md" in guide.source_files


@pytest.mark.asyncio
async def test_falls_back_to_readme(
    respx_mock: respx.MockRouter,
    github_client: GitHubClient,
) -> None:
    repo = "acme/sprockets"
    readme = """\
# Sprockets

## Setup

- Install Python 3.12
- `uv sync`
"""
    # Both contributing locations 404
    for p in (
        "CONTRIBUTING.md",
        "docs/CONTRIBUTING.md",
        ".github/CONTRIBUTING.md",
        "CONTRIBUTING.rst",
    ):
        respx_mock.get(f"/repos/{repo}/contents/{p}").mock(return_value=httpx.Response(404))
    respx_mock.get(f"/repos/{repo}/contents/README.md").mock(
        return_value=httpx.Response(
            200,
            json={
                "encoding": "base64",
                "content": _b64(readme),
            },
        )
    )

    guide = await get_contribution_guide(github_client, repo)

    assert any("uv sync" in step for step in guide.setup_instructions)
    assert "uv" in guide.required_tools
    assert guide.setup_complexity == "easy"
    assert "README.md" in guide.source_files
