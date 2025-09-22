"""CSV-based repository deduplication for GitHub crawler."""

import csv
import os
from datetime import datetime
from typing import Set, List, Dict, Any
from .logger import get_logger


class CSVDeduplicator:
    """Handles CSV-based repository deduplication to avoid re-scraping."""

    def __init__(self, csv_file_path: str = "database_exports/github_repositories_final.csv", hour_suffix: bool = True):
        """Initialize the CSV deduplicator.

        Args:
            csv_file_path: Path to the CSV file containing previously scraped repositories
            hour_suffix: If True, append current hour to filename (e.g., _h18)
        """
        if hour_suffix:
            from datetime import datetime
            current_hour = datetime.utcnow().hour

            # Insert hour suffix before file extension
            if csv_file_path.endswith('.csv'):
                base_path = csv_file_path[:-4]
                self.csv_file_path = f"{base_path}_h{current_hour}.csv"
            else:
                self.csv_file_path = f"{csv_file_path}_h{current_hour}"
        else:
            self.csv_file_path = csv_file_path
        self.logger = get_logger(__name__)
        self._known_repo_ids: Set[int] = set()
        self._loaded = False

    def load_existing_repository_ids(self) -> Set[int]:
        """Load repository IDs from ALL existing hourly CSV files.

        Returns:
            Set of repository IDs that have been previously scraped across all hours
        """
        if self._loaded:
            return self._known_repo_ids

        repo_ids = set()

        # Load from all hourly CSV files (h0 through h23) for complete deduplication
        csv_dir = os.path.dirname(self.csv_file_path) or "database_exports"
        base_name = "github_repositories_final"

        files_loaded = 0
        for hour in range(24):
            hourly_file = os.path.join(csv_dir, f"{base_name}_h{hour}.csv")

            if os.path.exists(hourly_file):
                try:
                    with open(hourly_file, 'r', newline='', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        file_repo_count = 0
                        for row in reader:
                            if 'id' in row and row['id']:
                                try:
                                    repo_id = int(row['id'])
                                    repo_ids.add(repo_id)
                                    file_repo_count += 1
                                except (ValueError, TypeError):
                                    continue

                    if file_repo_count > 0:
                        files_loaded += 1
                        self.logger.debug(
                            f"Loaded {file_repo_count} repos from {hourly_file}"
                        )

                except Exception as e:
                    self.logger.warning(
                        "Failed to load hourly CSV file",
                        csv_file=hourly_file,
                        error=str(e)
                    )

        # Also load from the main file (legacy support)
        main_file = os.path.join(csv_dir, f"{base_name}.csv")
        if os.path.exists(main_file):
            try:
                with open(main_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    main_file_count = 0
                    for row in reader:
                        if 'id' in row and row['id']:
                            try:
                                repo_id = int(row['id'])
                                repo_ids.add(repo_id)
                                main_file_count += 1
                            except (ValueError, TypeError):
                                continue

                if main_file_count > 0:
                    files_loaded += 1
                    self.logger.debug(f"Loaded {main_file_count} repos from main file")

            except Exception as e:
                self.logger.warning(
                    "Failed to load main CSV file",
                    csv_file=main_file,
                    error=str(e)
                )

        self.logger.info(
            "CSV deduplication loaded",
            hourly_files_found=files_loaded,
            total_known_repos=len(repo_ids),
            current_hour_file=self.csv_file_path
        )

        if len(repo_ids) == 0:
            self.logger.info("No existing CSV files found - starting fresh")

        self._known_repo_ids = repo_ids
        self._loaded = True
        return repo_ids

    def is_repository_known(self, repo_id: int) -> bool:
        """Check if a repository ID has been previously scraped.

        Args:
            repo_id: Repository ID to check

        Returns:
            True if repository was previously scraped, False otherwise
        """
        known_ids = self.load_existing_repository_ids()
        return repo_id in known_ids

    def filter_new_repositories(self, repositories) -> List:
        """Filter out repositories that have been previously scraped.

        Args:
            repositories: List of Repository domain objects

        Returns:
            List of Repository objects that are new (not previously scraped)
        """
        known_ids = self.load_existing_repository_ids()
        new_repos = []

        for repo in repositories:
            if repo.id not in known_ids:
                new_repos.append(repo)

        filtered_count = len(repositories) - len(new_repos)
        if filtered_count > 0:
            self.logger.info(
                "CSV deduplication filtered repositories",
                total_input=len(repositories),
                already_known=filtered_count,
                new_repositories=len(new_repos)
            )

        return new_repos

    def export_repositories_to_csv(self, repositories, run_id: str, matrix_index: int) -> bool:
        """Export repositories to CSV with run tracking.

        Args:
            repositories: List of Repository domain objects to export
            run_id: Unique identifier for this crawl run
            matrix_index: Matrix job index for tracking

        Returns:
            True if export successful, False otherwise
        """
        if not repositories:
            self.logger.info("No repositories to export to CSV")
            return True

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.csv_file_path), exist_ok=True)

            # Check if file exists to determine if we need headers
            file_exists = os.path.exists(self.csv_file_path)

            # CSV format: id,name,name_with_owner,url,created_at,stars,crawled_at
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8') as f:
                fieldnames = ['id', 'name', 'name_with_owner', 'url', 'created_at', 'stars', 'crawled_at']
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                # Write header only if file is new
                if not file_exists:
                    writer.writeheader()
                    self.logger.info("Created new CSV file with headers", csv_file=self.csv_file_path)

                # Add repositories with current timestamp
                current_time = datetime.utcnow().isoformat() + 'Z'

                for repo in repositories:
                    # Convert Repository domain object to CSV row
                    row = {
                        'id': repo.id,
                        'name': repo.name,
                        'name_with_owner': repo.name_with_owner,
                        'url': repo.url,
                        'created_at': repo.created_at,
                        'stars': repo.stars,
                        'crawled_at': current_time
                    }
                    writer.writerow(row)

                    # Update our in-memory cache
                    self._known_repo_ids.add(repo.id)

            self.logger.info(
                "Successfully exported repositories to CSV",
                csv_file=self.csv_file_path,
                count=len(repositories),
                run_id=run_id,
                matrix_index=matrix_index
            )

            return True

        except Exception as e:
            self.logger.error(
                "Failed to export repositories to CSV",
                csv_file=self.csv_file_path,
                error=str(e)
            )
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about all hourly CSV files.

        Returns:
            Dictionary with CSV statistics across all hours
        """
        stats = {
            "csv_exists": False,
            "total_repositories": 0,
            "hourly_files": 0,
            "current_hour_file": self.csv_file_path
        }

        csv_dir = os.path.dirname(self.csv_file_path) or "database_exports"
        base_name = "github_repositories_final"
        total_repos = 0
        files_found = 0

        # Check all hourly files
        for hour in range(24):
            hourly_file = os.path.join(csv_dir, f"{base_name}_h{hour}.csv")
            if os.path.exists(hourly_file):
                try:
                    with open(hourly_file, 'r', newline='', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        repo_count = sum(1 for row in reader)
                        total_repos += repo_count
                        files_found += 1
                except Exception as e:
                    self.logger.error(f"Failed to read {hourly_file}", error=str(e))

        # Check main file (legacy)
        main_file = os.path.join(csv_dir, f"{base_name}.csv")
        if os.path.exists(main_file):
            try:
                with open(main_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    main_repo_count = sum(1 for row in reader)
                    total_repos += main_repo_count
                    files_found += 1
            except Exception as e:
                self.logger.error(f"Failed to read {main_file}", error=str(e))

        stats["csv_exists"] = files_found > 0
        stats["total_repositories"] = total_repos
        stats["hourly_files"] = files_found

        return stats