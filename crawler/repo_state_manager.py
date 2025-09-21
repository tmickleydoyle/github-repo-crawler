"""
Repository-based state management for GitHub crawler.

This module stores crawler state in a separate GitHub repository,
providing reliable persistence and transparency without needing Gist permissions.
"""

import base64
import json
import logging
from datetime import datetime

import aiohttp

from .config import get_settings
from .state_manager import CrawlerState

logger = logging.getLogger(__name__)


class RepositoryStateManager:
    """Manages global crawler state using a GitHub repository."""

    def __init__(
        self,
        state_repo: str | None = None,
        state_branch: str = "main",
        state_file: str = "crawler_state.json",
        github_token: str | None = None,
    ):
        """Initialize repository state manager.

        Args:
            state_repo: GitHub repository in format "owner/repo" for storing state
            state_branch: Branch to store state on (default: main)
            state_file: Filename for state storage (default: crawler_state.json)
            github_token: GitHub token for repository access
        """
        settings = get_settings()
        self.github_token = github_token or settings.github_token.get_secret_value()
        self.state_repo = state_repo or settings.crawler_state_repo
        self.state_branch = state_branch
        self.state_file = state_file
        self.headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Crawler/1.0",
        }

    async def load_state(self) -> CrawlerState:
        """Load crawler state from repository."""
        if not self.state_repo:
            logger.info("No state repository configured, creating new state")
            return CrawlerState()

        try:
            async with aiohttp.ClientSession() as session:
                # Try to get the file from the repository
                url = f"https://api.github.com/repos/{self.state_repo}/contents/{self.state_file}"
                params = {"ref": self.state_branch}

                async with session.get(
                    url, headers=self.headers, params=params
                ) as resp:
                    if resp.status == 404:
                        logger.info(
                            f"State file not found in {self.state_repo}, creating new state"
                        )
                        return CrawlerState()

                    resp.raise_for_status()
                    data = await resp.json()

                    # Decode base64 content
                    content = base64.b64decode(data["content"]).decode("utf-8")
                    state_data = json.loads(content)

                    state = CrawlerState.from_dict(state_data)
                    logger.info(
                        f"Loaded state from {self.state_repo}: "
                        f"{len(state.partitions)} partitions, "
                        f"{state.total_repositories} total repos"
                    )
                    return state

        except Exception as e:
            logger.error(f"Failed to load state from repository {self.state_repo}: {e}")
            return CrawlerState()

    async def save_state(self, state: CrawlerState) -> str:
        """Save crawler state to repository.

        Returns:
            Repository name where state was saved
        """
        if not self.state_repo:
            raise ValueError("No state repository configured")

        state.last_updated = datetime.utcnow().isoformat()
        state_json = json.dumps(state.to_dict(), indent=2)

        try:
            async with aiohttp.ClientSession() as session:
                # First, try to get the current file to get its SHA (required for updates)
                url = f"https://api.github.com/repos/{self.state_repo}/contents/{self.state_file}"
                params = {"ref": self.state_branch}

                current_sha = None
                async with session.get(
                    url, headers=self.headers, params=params
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current_sha = data["sha"]
                    elif resp.status != 404:
                        resp.raise_for_status()

                # Prepare the commit payload
                payload = {
                    "message": f"Update crawler state - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                    "content": base64.b64encode(state_json.encode("utf-8")).decode(
                        "utf-8"
                    ),
                    "branch": self.state_branch,
                }

                if current_sha:
                    payload["sha"] = current_sha

                # Create or update the file
                async with session.put(url, headers=self.headers, json=payload) as resp:
                    resp.raise_for_status()

                    logger.info(f"Saved state to repository {self.state_repo}")
                    return self.state_repo

        except Exception as e:
            logger.error(f"Failed to save state to repository {self.state_repo}: {e}")
            raise

    async def record_workflow_run(
        self, state: CrawlerState, run_id: str, matrix_total: int, target_repos: int
    ) -> None:
        """Record a workflow run in the state."""
        run_info = {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "matrix_total": matrix_total,
            "target_repos": target_repos,
            "repositories_collected": 0,  # Will be updated at end
        }
        state.workflow_runs.append(run_info)

    def mark_partition_complete(
        self,
        state: CrawlerState,
        partition_id: str,
        repositories_found: int,
        exhausted: bool = False,
    ) -> None:
        """Mark a partition as complete or exhausted."""
        if partition_id in state.partitions:
            partition = state.partitions[partition_id]
            partition.status = "exhausted" if exhausted else "completed"
            partition.repositories_found = repositories_found
            partition.completed_at = datetime.utcnow().isoformat()
            state.total_repositories += repositories_found
            logger.info(
                f"Partition {partition_id} marked as {partition.status} "
                f"with {repositories_found} repositories"
            )

    async def create_state_repository(
        self, repo_name: str, description: str = None
    ) -> str:
        """Create a new repository for state storage.

        Args:
            repo_name: Name for the new repository
            description: Optional description for the repository

        Returns:
            Full repository name (owner/repo)
        """
        if description is None:
            description = (
                "GitHub Crawler State Storage - Automated repository discovery tracking"
            )

        try:
            async with aiohttp.ClientSession() as session:
                # Create the repository
                url = "https://api.github.com/user/repos"
                payload = {
                    "name": repo_name,
                    "description": description,
                    "private": True,  # Keep state private
                    "auto_init": True,  # Initialize with README
                }

                async with session.post(
                    url, headers=self.headers, json=payload
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

                    full_name = data["full_name"]
                    logger.info(f"Created state repository: {full_name}")

                    # Initialize with empty state
                    self.state_repo = full_name
                    initial_state = CrawlerState()
                    await self.save_state(initial_state)

                    return full_name

        except Exception as e:
            logger.error(f"Failed to create state repository: {e}")
            raise

    async def get_repository_info(self) -> dict:
        """Get information about the state repository."""
        if not self.state_repo:
            return {"error": "No state repository configured"}

        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.github.com/repos/{self.state_repo}"
                async with session.get(url, headers=self.headers) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

                    return {
                        "name": data["full_name"],
                        "description": data["description"],
                        "private": data["private"],
                        "url": data["html_url"],
                        "created_at": data["created_at"],
                        "updated_at": data["updated_at"],
                        "size": data["size"],
                    }

        except Exception as e:
            logger.error(f"Failed to get repository info: {e}")
            return {"error": str(e)}
