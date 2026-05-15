"""`get_contribution_guide` MCP tool — CONTRIBUTING.md parser + summariser."""

from __future__ import annotations

import re

from gfi_scout.models.issue import ContributionGuide
from gfi_scout.services.github_api import GitHubClient
from gfi_scout.utils.logger import get_logger
from gfi_scout.utils.validators import validate_repo_full_name

log = get_logger(__name__)

CONTRIBUTING_PATHS = (
    "CONTRIBUTING.md",
    "docs/CONTRIBUTING.md",
    ".github/CONTRIBUTING.md",
    "CONTRIBUTING.rst",
)
README_PATHS = ("README.md", "readme.md", "Readme.md", "README.rst")
SETUP_SECTION_RE = re.compile(
    r"#+\s*(installation|installing|getting\s+started|setup|development|"
    r"local\s+development|build|run)",
    re.IGNORECASE,
)
TEST_SECTION_RE = re.compile(
    r"#+\s*(testing|tests|running\s+tests)",
    re.IGNORECASE,
)
PR_SECTION_RE = re.compile(
    r"#+\s*(pull\s+requests?|pr\s+process|submitting\s+changes|"
    r"commit|branch)",
    re.IGNORECASE,
)
TOOL_KEYWORDS = (
    "node",
    "npm",
    "pnpm",
    "yarn",
    "bun",
    "python",
    "uv",
    "pip",
    "poetry",
    "go",
    "rust",
    "cargo",
    "make",
    "docker",
    "java",
    "maven",
    "gradle",
    "ruby",
    "bundler",
)
COMPLEXITY_HINTS_HARD = (
    "docker compose",
    "kubernetes",
    "kafka",
    "postgres",
    "mysql",
    "redis cluster",
    "multiple services",
    "submodule",
)
COMPLEXITY_HINTS_MODERATE = (
    "docker",
    "database",
    "redis",
    "env file",
    "compile",
    "build step",
)
BULLET_RE = re.compile(r"^[\s>]*[-*+\d.]+\s+(.+)$")


def _extract_section(text: str, heading_re: re.Pattern[str]) -> list[str]:
    """Extract bullet/numbered lines from sections whose heading matches."""
    if not text:
        return []
    lines = text.splitlines()
    capture = False
    captured: list[str] = []
    for line in lines:
        stripped = line.rstrip()
        if re.match(r"^#+\s", stripped):
            capture = bool(heading_re.match(stripped))
            continue
        if capture and stripped.strip():
            bullet = BULLET_RE.match(stripped)
            content = bullet.group(1) if bullet else stripped.strip()
            if content:
                captured.append(content)
    # de-dupe while preserving order, cap to keep payload small
    seen: set[str] = set()
    out: list[str] = []
    for item in captured:
        if item not in seen:
            seen.add(item)
            out.append(item)
        if len(out) >= 12:
            break
    return out


def _detect_tools(text: str) -> list[str]:
    if not text:
        return []
    lowered = text.lower()
    return [tool for tool in TOOL_KEYWORDS if tool in lowered]


def _estimate_complexity(text: str) -> str:
    lowered = (text or "").lower()
    if any(hint in lowered for hint in COMPLEXITY_HINTS_HARD):
        return "complex"
    if any(hint in lowered for hint in COMPLEXITY_HINTS_MODERATE):
        return "moderate"
    return "easy"


def _summarise(text: str, *, limit_chars: int = 600) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    summary_parts: list[str] = []
    for para in paragraphs:
        if para.startswith("#"):
            continue
        summary_parts.append(para)
        if sum(len(p) for p in summary_parts) > limit_chars:
            break
    summary = "\n\n".join(summary_parts)[:limit_chars].rstrip()
    if len(summary) >= limit_chars:
        summary = summary.rstrip() + "…"
    return summary


async def _fetch_first_existing(
    client: GitHubClient,
    repo: str,
    paths: tuple[str, ...],
) -> tuple[str | None, str | None]:
    for path in paths:
        text = await client.get_content_text(repo, path)
        if text:
            return text, path
    return None, None


async def get_contribution_guide(
    client: GitHubClient,
    repo: str,
) -> ContributionGuide:
    """Pull CONTRIBUTING.md (or README setup section) and summarise it."""
    full_name = validate_repo_full_name(repo)
    log.info("get_contribution_guide repo=%s", full_name)

    contributing_text, contributing_path = await _fetch_first_existing(
        client,
        full_name,
        CONTRIBUTING_PATHS,
    )
    readme_text, readme_path = await _fetch_first_existing(
        client,
        full_name,
        README_PATHS,
    )

    primary = contributing_text or readme_text or ""
    source_files = [p for p in (contributing_path, readme_path) if p]

    setup = _extract_section(primary, SETUP_SECTION_RE)
    if not setup and readme_text and readme_text is not primary:
        setup = _extract_section(readme_text, SETUP_SECTION_RE)

    tests = _extract_section(primary, TEST_SECTION_RE)
    if not tests and readme_text and readme_text is not primary:
        tests = _extract_section(readme_text, TEST_SECTION_RE)

    pr_conventions = _extract_section(primary, PR_SECTION_RE)
    tools = _detect_tools(primary + "\n" + (readme_text or ""))
    complexity = _estimate_complexity(primary + "\n" + (readme_text or ""))
    summary = _summarise(primary)

    return ContributionGuide(
        repo_full_name=full_name,
        contributing_summary=summary,
        setup_instructions=setup,
        testing_requirements=tests,
        pr_conventions=pr_conventions,
        required_tools=tools,
        setup_complexity=complexity,
        source_files=source_files,
    )
