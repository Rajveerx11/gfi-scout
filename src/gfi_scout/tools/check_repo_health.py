"""`check_repo_health` MCP tool."""

from __future__ import annotations

from gfi_scout.models.repo import RepoHealth
from gfi_scout.services.github_api import GitHubClient
from gfi_scout.services.repo_analyzer import analyse_repo
from gfi_scout.services.scoring_config import ScoringConfig
from gfi_scout.utils.logger import get_logger
from gfi_scout.utils.validators import validate_repo_full_name

log = get_logger(__name__)


async def check_repo_health(
    client: GitHubClient,
    repo: str,
    *,
    cfg: ScoringConfig,
    pr_sample_size: int = 50,
) -> RepoHealth:
    """Analyse a repo for contributor-friendliness signals.

    Phase 2: aggregates merge rate, recent activity, CONTRIBUTING/CoC/CI
    presence into an A-F grade. Pulls all of it from GitHub's REST API.
    """
    full_name = validate_repo_full_name(repo)
    log.info("check_repo_health repo=%s", full_name)
    return await analyse_repo(
        client,
        full_name,
        cfg=cfg,
        pr_sample_size=pr_sample_size,
    )
