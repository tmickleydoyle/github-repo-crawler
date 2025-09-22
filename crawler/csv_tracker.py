"""CSV-based repository tracking for deduplication."""

import csv
import os
from datetime import datetime
from typing import Set, List, Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class CSVRepositoryTracker:
    """Manages tracking of scraped repositories using CSV files for deduplication."""

    def __init__(self, csv_file_path: str = "github_repositories_final.csv"):
        self.csv_file_path = csv_file_path
        self._known_repo_ids: Set[int] = set()
        self._loaded = False

    def _load_existing_repositories(self) -> Set[int]:
        """Load repository IDs from existing CSV file."""
        if self._loaded:
            return self._known_repo_ids

        repo_ids = set()

        if os.path.exists(self.csv_file_path):
            try:
                with open(self.csv_file_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Try to get ID from different possible column names
                        repo_id = None
                        for id_col in ['id', 'repo_id', 'databaseId']:
                            if id_col in row and row[id_col]:
                                try:
                                    repo_id = int(row[id_col])
                                    break
                                except (ValueError, TypeError):
                                    continue

                        if repo_id:
                            repo_ids.add(repo_id)

                logger.info("Loaded existing repositories for deduplication",
                          csv_file=self.csv_file_path,
                          count=len(repo_ids))

            except Exception as e:
                logger.warning("Failed to load existing CSV file",
                             csv_file=self.csv_file_path,
                             error=str(e))

        else:
            logger.info("No existing CSV file found - starting fresh",
                       csv_file=self.csv_file_path)

        self._known_repo_ids = repo_ids
        self._loaded = True
        return repo_ids

    def get_known_repository_ids(self) -> Set[int]:
        """Get all known repository IDs from previous runs."""
        return self._load_existing_repositories()

    def is_repository_known(self, repo_id: int) -> bool:
        """Check if a repository ID is already known."""
        known_ids = self.get_known_repository_ids()
        return repo_id in known_ids

    def filter_new_repositories(self, repositories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out repositories that are already known."""
        known_ids = self.get_known_repository_ids()
        new_repos = []

        for repo in repositories:
            repo_id = repo.get('id')
            if repo_id and repo_id not in known_ids:
                new_repos.append(repo)

        logger.info("Filtered repositories using CSV tracking",
                   total_input=len(repositories),
                   already_known=len(repositories) - len(new_repos),
                   new_repositories=len(new_repos))

        return new_repos

    def append_repositories_to_csv(self,
                                  repositories: List[Dict[str, Any]],
                                  run_id: str,
                                  matrix_index: int) -> bool:
        """Append new repositories to the CSV file with run tracking."""
        if not repositories:
            logger.info("No repositories to append to CSV")
            return True

        try:
            # Check if file exists to determine if we need headers
            file_exists = os.path.exists(self.csv_file_path)

            # Determine fieldnames based on first repository and add tracking fields
            if repositories:
                fieldnames = list(repositories[0].keys())
                # Add tracking fields if not present
                if 'run_id' not in fieldnames:
                    fieldnames.append('run_id')
                if 'matrix_index' not in fieldnames:
                    fieldnames.append('matrix_index')
                if 'discovered_at' not in fieldnames:
                    fieldnames.append('discovered_at')
            else:
                fieldnames = ['id', 'name', 'name_with_owner', 'url', 'created_at', 'stars', 'forks',
                             'language', 'owner', 'license', 'pushed_at', 'updated_at',
                             'run_id', 'matrix_index', 'discovered_at']

            # Open file in append mode
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                # Write header only if file is new
                if not file_exists:
                    writer.writeheader()
                    logger.info("Created new CSV file with headers", csv_file=self.csv_file_path)

                # Add tracking information and write repositories
                current_time = datetime.utcnow().isoformat() + 'Z'

                for repo in repositories:
                    # Add tracking fields
                    repo_with_tracking = repo.copy()
                    repo_with_tracking['run_id'] = run_id
                    repo_with_tracking['matrix_index'] = matrix_index
                    repo_with_tracking['discovered_at'] = current_time

                    writer.writerow(repo_with_tracking)

                    # Update our in-memory cache
                    if repo.get('id'):
                        self._known_repo_ids.add(repo['id'])

            logger.info("Successfully appended repositories to CSV",
                       csv_file=self.csv_file_path,
                       count=len(repositories),
                       run_id=run_id,
                       matrix_index=matrix_index)

            return True

        except Exception as e:
            logger.error("Failed to append repositories to CSV",
                        csv_file=self.csv_file_path,
                        error=str(e))
            return False

    def get_csv_stats(self) -> Dict[str, Any]:
        """Get statistics about the CSV tracking file."""
        stats = {
            "csv_exists": False,
            "total_repositories": 0,
            "unique_run_ids": 0,
            "latest_run_id": None,
            "earliest_run_id": None,
        }

        if not os.path.exists(self.csv_file_path):
            return stats

        try:
            stats["csv_exists"] = True
            run_ids = set()
            repo_count = 0

            with open(self.csv_file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    repo_count += 1
                    if 'run_id' in row and row['run_id']:
                        run_ids.add(row['run_id'])

            stats["total_repositories"] = repo_count
            stats["unique_run_ids"] = len(run_ids)

            if run_ids:
                sorted_runs = sorted(run_ids)
                stats["earliest_run_id"] = sorted_runs[0]
                stats["latest_run_id"] = sorted_runs[-1]

        except Exception as e:
            logger.error("Failed to get CSV stats", error=str(e))

        return stats

    def generate_run_id(self, matrix_total: int, matrix_index: int) -> str:
        """Generate a unique run ID for tracking."""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return f"run-{timestamp}-{matrix_total}jobs"