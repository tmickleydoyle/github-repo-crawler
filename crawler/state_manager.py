"""
Global state management for GitHub crawler using GitHub Gists as free persistent storage.

This module provides a way to track crawling progress across multiple workflow runs,
preventing duplicate work and ensuring systematic coverage of the entire GitHub repository space.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import aiohttp

from .config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SearchSpacePartition:
    """Represents a unique search space partition."""

    partition_id: str
    query: str
    status: str  # pending, in_progress, completed, exhausted
    repositories_found: int = 0
    last_cursor: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error_count: int = 0
    last_error: str | None = None


@dataclass
class CrawlerState:
    """Global crawler state stored in GitHub Gist."""

    version: int = 1
    total_repositories: int = 0
    total_unique_repositories: set[int] = field(default_factory=set)
    partitions: dict[str, SearchSpacePartition] = field(default_factory=dict)
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    workflow_runs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "total_repositories": self.total_repositories,
            "total_unique_repositories": len(self.total_unique_repositories),
            "unique_repo_ids": list(self.total_unique_repositories)[:1000],  # Sample for size
            "partitions": {k: asdict(v) for k, v in self.partitions.items()},
            "last_updated": self.last_updated,
            "workflow_runs": self.workflow_runs[-50:],  # Keep last 50 runs
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CrawlerState":
        """Create from dictionary."""
        state = cls(
            version=data.get("version", 1),
            total_repositories=data.get("total_repositories", 0),
            total_unique_repositories=set(data.get("unique_repo_ids", [])),
            last_updated=data.get("last_updated", datetime.utcnow().isoformat()),
            workflow_runs=data.get("workflow_runs", []),
        )

        for pid, pdata in data.get("partitions", {}).items():
            state.partitions[pid] = SearchSpacePartition(**pdata)

        return state


class StateManager:
    """Manages global crawler state using GitHub Gists."""

    def __init__(self, gist_id: str | None = None, github_token: str | None = None):
        """Initialize state manager.

        Args:
            gist_id: GitHub Gist ID for storing state. If None, will create new gist.
            github_token: GitHub token for Gist API access.
        """
        settings = get_settings()
        self.github_token = github_token or settings.github_token.get_secret_value()
        self.gist_id = gist_id or settings.crawler_state_gist_id
        self.state_filename = "crawler_state.json"
        self.headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def load_state(self) -> CrawlerState:
        """Load crawler state from GitHub Gist."""
        if not self.gist_id:
            logger.info("No Gist ID configured, creating new state")
            return CrawlerState()

        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.github.com/gists/{self.gist_id}"
                async with session.get(url, headers=self.headers) as resp:
                    if resp.status == 404:
                        logger.warning(f"Gist {self.gist_id} not found, creating new state")
                        return CrawlerState()

                    resp.raise_for_status()
                    data = await resp.json()

                    if self.state_filename in data.get("files", {}):
                        content = data["files"][self.state_filename]["content"]
                        state_data = json.loads(content)
                        state = CrawlerState.from_dict(state_data)
                        logger.info(
                            f"Loaded state: {len(state.partitions)} partitions, "
                            f"{state.total_repositories} total repos"
                        )
                        return state
                    else:
                        logger.warning("State file not found in Gist, creating new state")
                        return CrawlerState()

        except Exception as e:
            logger.error(f"Failed to load state from Gist: {e}")
            return CrawlerState()

    async def save_state(self, state: CrawlerState) -> str:
        """Save crawler state to GitHub Gist.

        Returns:
            Gist ID (useful if new gist was created)
        """
        state.last_updated = datetime.utcnow().isoformat()
        state_json = json.dumps(state.to_dict(), indent=2)

        files = {
            self.state_filename: {
                "content": state_json
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                if self.gist_id:
                    # Update existing gist
                    url = f"https://api.github.com/gists/{self.gist_id}"
                    payload = {"files": files}
                    async with session.patch(url, headers=self.headers, json=payload) as resp:
                        resp.raise_for_status()
                        logger.info(f"Updated state in Gist {self.gist_id}")
                        return self.gist_id
                else:
                    # Create new gist
                    url = "https://api.github.com/gists"
                    payload = {
                        "description": "GitHub Crawler State - Automated tracking of repository discovery",
                        "public": False,
                        "files": files
                    }
                    async with session.post(url, headers=self.headers, json=payload) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        self.gist_id = data["id"]
                        logger.info(f"Created new state Gist: {self.gist_id}")
                        logger.info("⚠️ Add CRAWLER_STATE_GIST_ID to your repository secrets!")
                        return self.gist_id

        except Exception as e:
            logger.error(f"Failed to save state to Gist: {e}")
            raise

    async def record_workflow_run(
        self,
        state: CrawlerState,
        run_id: str,
        matrix_total: int,
        target_repos: int
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

    def get_next_partition(self, state: CrawlerState, matrix_index: int, matrix_total: int) -> SearchSpacePartition | None:
        """Get the next partition for a matrix job to work on."""
        # Find pending partitions
        pending_partitions = [
            p for p in state.partitions.values()
            if p.status == "pending"
        ]

        if not pending_partitions:
            logger.warning("No pending partitions available")
            return None

        # Distribute partitions across matrix jobs
        partition_index = matrix_index % len(pending_partitions)
        if partition_index < len(pending_partitions):
            return pending_partitions[partition_index]

        return None

    def mark_partition_complete(
        self,
        state: CrawlerState,
        partition_id: str,
        repositories_found: int,
        exhausted: bool = False
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