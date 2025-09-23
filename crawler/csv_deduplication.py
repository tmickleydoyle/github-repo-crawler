"""CSV-based repository deduplication for GitHub crawler."""

import csv
import os
from datetime import datetime
from typing import Any

from .logger import get_logger


class CSVDeduplicator:
    """Handles CSV-based repository deduplication to avoid re-scraping."""

    def __init__(
        self,
        csv_file_path: str = "database_exports/github_repositories_final.csv",
        hour_suffix: bool = True,
        matrix_index: int | None = None,
    ):
        """Initialize the CSV deduplicator.

        Args:
            csv_file_path: Path to CSV file with previously scraped repositories
            hour_suffix: If True, append current hour to filename (e.g., _h18)
            matrix_index: If provided, append matrix index for individual job files
        """
        if hour_suffix:
            from datetime import datetime

            current_hour = datetime.utcnow().hour

            # Insert hour suffix before file extension
            if csv_file_path.endswith(".csv"):
                base_path = csv_file_path[:-4]
                if matrix_index is not None:
                    # Individual matrix job file (e.g., _h18_matrix0.csv)
                    self.csv_file_path = (
                        f"{base_path}_h{current_hour}_matrix{matrix_index}.csv"
                    )
                else:
                    # Final consolidated hour file (e.g., _h18.csv)
                    self.csv_file_path = f"{base_path}_h{current_hour}.csv"
            else:
                if matrix_index is not None:
                    self.csv_file_path = (
                        f"{csv_file_path}_h{current_hour}_matrix{matrix_index}"
                    )
                else:
                    self.csv_file_path = f"{csv_file_path}_h{current_hour}"
        else:
            self.csv_file_path = csv_file_path
        self.logger = get_logger(__name__)
        self._known_repo_ids: set[int] = set()
        self._loaded = False

    def load_existing_repository_ids(self) -> set[int]:
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
                    with open(hourly_file, newline="", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        file_repo_count = 0
                        for row in reader:
                            if row.get("id"):
                                try:
                                    repo_id = int(row["id"])
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
                        error=str(e),
                    )

        # Also load from the main file (legacy support)
        main_file = os.path.join(csv_dir, f"{base_name}.csv")
        if os.path.exists(main_file):
            try:
                with open(main_file, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    main_file_count = 0
                    for row in reader:
                        if row.get("id"):
                            try:
                                repo_id = int(row["id"])
                                repo_ids.add(repo_id)
                                main_file_count += 1
                            except (ValueError, TypeError):
                                continue

                if main_file_count > 0:
                    files_loaded += 1
                    self.logger.debug(f"Loaded {main_file_count} repos from main file")

            except Exception as e:
                self.logger.warning(
                    "Failed to load main CSV file", csv_file=main_file, error=str(e)
                )

        self.logger.info(
            "CSV deduplication loaded",
            hourly_files_found=files_loaded,
            total_known_repos=len(repo_ids),
            current_hour_file=self.csv_file_path,
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

    def filter_new_repositories(self, repositories: list[Any]) -> list[Any]:
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
                new_repositories=len(new_repos),
            )

        return new_repos

    def export_repositories_to_csv(
        self, repositories: list[Any], run_id: str, matrix_index: int
    ) -> bool:
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
            with open(self.csv_file_path, "a", newline="", encoding="utf-8") as f:
                fieldnames = [
                    "id",
                    "name",
                    "name_with_owner",
                    "url",
                    "created_at",
                    "stars",
                    "crawled_at",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                # Write header only if file is new
                if not file_exists:
                    writer.writeheader()
                    self.logger.info(
                        "Created new CSV file with headers", csv_file=self.csv_file_path
                    )

                # Add repositories with current timestamp
                current_time = datetime.utcnow().isoformat() + "Z"

                for repo in repositories:
                    # Convert Repository domain object to CSV row
                    row = {
                        "id": repo.id,
                        "name": repo.name,
                        "name_with_owner": repo.name_with_owner,
                        "url": repo.url,
                        "created_at": repo.created_at,
                        "stars": repo.stars,
                        "crawled_at": current_time,
                    }
                    writer.writerow(row)

                    # Update our in-memory cache
                    self._known_repo_ids.add(repo.id)

            self.logger.info(
                "Successfully exported repositories to CSV",
                csv_file=self.csv_file_path,
                count=len(repositories),
                run_id=run_id,
                matrix_index=matrix_index,
            )

            return True

        except Exception as e:
            self.logger.error(
                "Failed to export repositories to CSV",
                csv_file=self.csv_file_path,
                error=str(e),
            )
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about all hourly CSV files.

        Returns:
            Dictionary with CSV statistics across all hours
        """
        stats = {
            "csv_exists": False,
            "total_repositories": 0,
            "hourly_files": 0,
            "current_hour_file": self.csv_file_path,
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
                    with open(hourly_file, newline="", encoding="utf-8") as f:
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
                with open(main_file, newline="", encoding="utf-8") as f:
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

    @staticmethod
    def consolidate_matrix_results(
        matrix_total: int, current_hour: int | None = None
    ) -> bool:
        """Consolidate all matrix job CSV files into a single hour file.

        This method merges individual matrix job CSV files (e.g., _h18_matrix0.csv,
        _h18_matrix1.csv) into a single consolidated hour file (_h18.csv).

        Args:
            matrix_total: Total number of matrix jobs to consolidate
            current_hour: Hour to consolidate (defaults to current UTC hour)

        Returns:
            True if consolidation successful, False otherwise
        """
        logger = get_logger(__name__)

        if current_hour is None:
            current_hour = datetime.utcnow().hour

        csv_dir = "database_exports"
        base_name = "github_repositories_final"
        final_file = os.path.join(csv_dir, f"{base_name}_h{current_hour}.csv")

        # Find all matrix job files for this hour
        matrix_files = []
        for matrix_index in range(matrix_total):
            matrix_file = os.path.join(
                csv_dir, f"{base_name}_h{current_hour}_matrix{matrix_index}.csv"
            )
            if os.path.exists(matrix_file):
                matrix_files.append(matrix_file)

        if not matrix_files:
            logger.warning(
                "No matrix job files found for consolidation",
                hour=current_hour,
                expected_files=matrix_total,
            )
            return False

        try:
            # Ensure output directory exists
            os.makedirs(csv_dir, exist_ok=True)

            # Consolidate all matrix files into final file
            total_repos = 0
            seen_repo_ids = set()

            with open(final_file, "w", newline="", encoding="utf-8") as output_file:
                fieldnames = [
                    "id",
                    "name",
                    "name_with_owner",
                    "url",
                    "created_at",
                    "stars",
                    "crawled_at",
                ]
                writer = csv.DictWriter(output_file, fieldnames=fieldnames)
                writer.writeheader()

                for matrix_file in matrix_files:
                    logger.debug(f"Processing matrix file: {matrix_file}")

                    try:
                        with open(
                            matrix_file, "r", newline="", encoding="utf-8"
                        ) as input_file:
                            reader = csv.DictReader(input_file)
                            file_repo_count = 0

                            for row in reader:
                                repo_id = row.get("id")
                                if repo_id and repo_id not in seen_repo_ids:
                                    try:
                                        # Validate repo_id is numeric
                                        int(repo_id)
                                        writer.writerow(row)
                                        seen_repo_ids.add(repo_id)
                                        file_repo_count += 1
                                        total_repos += 1
                                    except (ValueError, TypeError):
                                        logger.warning(f"Invalid repo ID: {repo_id}")
                                        continue

                            logger.debug(
                                f"Processed {file_repo_count} repos from {matrix_file}"
                            )

                    except Exception as e:
                        logger.error(
                            f"Failed to process matrix file {matrix_file}", error=str(e)
                        )

            # Clean up individual matrix files after successful consolidation
            for matrix_file in matrix_files:
                try:
                    os.remove(matrix_file)
                    logger.debug(f"Removed matrix file: {matrix_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove {matrix_file}", error=str(e))

            logger.info(
                "Successfully consolidated matrix job results",
                hour=current_hour,
                matrix_files_processed=len(matrix_files),
                total_repositories=total_repos,
                final_file=final_file,
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to consolidate matrix job results",
                hour=current_hour,
                error=str(e),
            )
            return False
