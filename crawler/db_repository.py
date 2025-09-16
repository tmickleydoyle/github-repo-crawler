"""Repository pattern for centralized database operations."""

from datetime import UTC, date, datetime
from typing import Any

import asyncpg
from asyncpg import Connection, Pool

from .config import get_settings
from .domain import CrawlResult
from .domain import Repository as RepoModel
from .logger import get_logger


class DatabaseRepository:
    """Centralized repository for all database operations.

    This class implements the repository pattern to centralize all database
    logic, making it easier for junior engineers to maintain and understand
    the codebase. All database operations go through this single interface.
    """

    def __init__(self, pool: Pool | None = None):
        """Initialize the database repository.

        Args:
            pool: Optional connection pool. If not provided, connections
                  will be created as needed.
        """
        self.pool = pool
        self.settings = get_settings()
        self.logger = get_logger(__name__)

    async def create_pool(self) -> Pool:
        """Create a database connection pool.

        Returns:
            Configured asyncpg connection pool
        """
        # Optimize pool settings for high-concurrency matrix runs
        concurrent_requests = getattr(self.settings, "crawler_concurrent_requests", 10)

        return await asyncpg.create_pool(
            host=self.settings.database_host,
            port=self.settings.database_port,
            user=self.settings.database_username,
            password=self.settings.database_password.get_secret_value(),
            database=self.settings.database_name,
            # Scale pool size based on concurrency needs
            min_size=max(5, concurrent_requests // 2),
            max_size=min(
                50, max(self.settings.database_pool_size, concurrent_requests * 2)
            ),
            # Reduce timeout for faster failures and connection recycling
            command_timeout=30,
            # Add connection lifecycle management for better performance
            max_inactive_connection_lifetime=300,  # 5 minutes
            # Optimize for GitHub Actions environment - only set safe runtime parameters
            server_settings={"jit": "off"},
        )

    async def get_connection(self) -> Connection:
        """Get a database connection.

        Returns:
            Database connection (either from pool or direct)
        """
        if self.pool:
            return await self.pool.acquire()
        return await asyncpg.connect(
            host=self.settings.database_host,
            port=self.settings.database_port,
            user=self.settings.database_username,
            password=self.settings.database_password.get_secret_value(),
            database=self.settings.database_name,
        )

    async def release_connection(self, conn: Connection) -> None:
        """Release a database connection.

        Args:
            conn: Connection to release
        """
        if self.pool:
            await self.pool.release(conn)
        else:
            await conn.close()

    async def initialize_schema(self) -> None:
        """Initialize the database schema.

        Creates all necessary tables and indexes if they don't exist.
        This centralizes schema management in one place.
        """
        self.logger.info("Starting schema initialization")
        conn = await self.get_connection()
        try:
            # Create main repository table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS repo (
                    id BIGINT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    url TEXT NOT NULL,
                    created_at TIMESTAMP,
                    alphabet_partition VARCHAR(100),
                    name_with_owner TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create statistics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS repo_stats (
                    repo_id BIGINT NOT NULL REFERENCES repo(id) ON DELETE CASCADE,
                    fetched_date DATE NOT NULL,
                    stars INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(repo_id, fetched_date)
                )
            """)

            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_repo_stars ON repo (id)",
                "CREATE INDEX IF NOT EXISTS idx_repo_name_with_owner ON repo (name_with_owner)",
                "CREATE INDEX IF NOT EXISTS idx_repo_alphabet_partition ON repo (alphabet_partition)",
                "CREATE INDEX IF NOT EXISTS idx_repo_owner ON repo (owner)",
                "CREATE INDEX IF NOT EXISTS idx_repo_stats_date ON repo_stats (fetched_date)",
                "CREATE INDEX IF NOT EXISTS idx_repo_stats_repo_id ON repo_stats (repo_id)",
            ]

            for index_sql in indexes:
                await conn.execute(index_sql)

            self.logger.info("Database schema initialized successfully")

        finally:
            await self.release_connection(conn)

    async def store_repositories(
        self,
        crawl_result: CrawlResult,
        matrix_index: int = 0,
    ) -> dict[str, Any]:
        """Store repositories and their statistics.

        This is the main method for storing crawled data. It handles both
        repository metadata and star statistics in a single transaction.

        Args:
            crawl_result: The crawl result containing repositories
            matrix_index: Index of the matrix job for partitioning

        Returns:
            Dictionary with storage statistics
        """
        import time

        start_time = time.time()
        self.logger.info(
            "Starting repository storage",
            matrix_index=matrix_index,
            repo_count=len(crawl_result.repositories),
        )

        conn = await self.get_connection()
        try:
            current_date = datetime.now(UTC).date()
            stats = {
                "successful": 0,
                "failed": 0,
                "total": len(crawl_result.repositories),
            }

            if not crawl_result.repositories:
                self.logger.warning("No repositories to store - crawl result is empty!")
                return stats

            async with conn.transaction():
                # Use individual inserts for reliability (matches working version)
                for repo in crawl_result.repositories:
                    try:
                        await self._store_single_repository(
                            conn, repo, matrix_index, current_date
                        )
                        stats["successful"] += 1
                    except Exception as e:
                        stats["failed"] += 1
                        self.logger.error(
                            "Failed to store repository",
                            repo_id=repo.id,
                            repo_name=repo.name,
                            error=str(e),
                        )

                self.logger.info(
                    "Repository storage completed",
                    successful=stats["successful"],
                    failed=stats["failed"],
                    total_repositories=len(crawl_result.repositories),
                    unique_owners=crawl_result.unique_owners,
                    total_stars=crawl_result.total_stars,
                    average_stars=round(crawl_result.average_stars, 1),
                )

            duration = time.time() - start_time
            self.logger.info(
                "Repository storage completed",
                **stats,
                unique_owners=crawl_result.unique_owners,
                total_stars=crawl_result.total_stars,
                average_stars=round(crawl_result.average_stars, 1),
                duration_seconds=round(duration, 3),
            )

            return stats

        finally:
            await self.release_connection(conn)

    async def _store_single_repository(
        self,
        conn: Connection,
        repo: RepoModel,
        matrix_index: int,
        current_date: date,
    ) -> None:
        """Store a single repository and its statistics.

        Internal method to store one repository. Separated for clarity
        and easier testing.

        Args:
            conn: Database connection
            repo: Repository to store
            matrix_index: Matrix job index
            current_date: Current date for statistics
        """
        # Parse datetime safely
        created_at = self._parse_github_datetime(repo.created_at)

        # Upsert repository
        await conn.execute(
            """
            INSERT INTO repo
            (id, name, owner, url, created_at, name_with_owner, alphabet_partition)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
                name_with_owner = EXCLUDED.name_with_owner,
                alphabet_partition = EXCLUDED.alphabet_partition,
                last_updated = CURRENT_TIMESTAMP
        """,
            repo.id,
            repo.name,
            repo.owner,
            repo.url,
            created_at,
            repo.name_with_owner,
            f"matrix_{matrix_index}",
        )

        # Upsert statistics
        await conn.execute(
            """
            INSERT INTO repo_stats (repo_id, fetched_date, stars)
            VALUES ($1, $2, $3)
            ON CONFLICT (repo_id, fetched_date) DO UPDATE SET
                stars = EXCLUDED.stars
        """,
            repo.id,
            current_date,
            repo.stars,
        )

    def _parse_github_datetime(
        self, dt_input: str | datetime | None
    ) -> datetime | None:
        """Parse GitHub datetime to timezone-naive format for PostgreSQL.

        Args:
            dt_input: DateTime input (string or datetime object)

        Returns:
            Timezone-naive datetime or None
        """
        if not dt_input:
            return None

        if isinstance(dt_input, datetime):
            if dt_input.tzinfo:
                return dt_input.astimezone(UTC).replace(tzinfo=None)
            return dt_input

        if isinstance(dt_input, str):
            dt_aware = datetime.fromisoformat(dt_input.replace("Z", "+00:00"))
            return dt_aware.astimezone(UTC).replace(tzinfo=None)

        return None

    async def get_repository_by_id(self, repo_id: int) -> dict[str, Any] | None:
        """Get a repository by its ID.

        Args:
            repo_id: Repository ID

        Returns:
            Repository data or None if not found
        """
        conn = await self.get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM repo WHERE id = $1",
                repo_id,
            )
            return dict(row) if row else None
        finally:
            await self.release_connection(conn)

    async def get_repository_stats(
        self,
        repo_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Get star statistics for a repository.

        Args:
            repo_id: Repository ID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of statistics records
        """
        conn = await self.get_connection()
        try:
            query = "SELECT * FROM repo_stats WHERE repo_id = $1"
            params: list[int | date] = [repo_id]

            if start_date:
                query += f" AND fetched_date >= ${len(params) + 1}"
                params.append(start_date)

            if end_date:
                query += f" AND fetched_date <= ${len(params) + 1}"
                params.append(end_date)

            query += " ORDER BY fetched_date"

            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

        finally:
            await self.release_connection(conn)

    async def get_total_repository_count(self) -> int:
        """Get the total number of repositories in the database.

        Returns:
            Total repository count
        """
        conn = await self.get_connection()
        try:
            result = await conn.fetchval("SELECT COUNT(*) FROM repo")
            return result or 0
        finally:
            await self.release_connection(conn)

    async def get_repositories_by_owner(self, owner: str) -> list[dict[str, Any]]:
        """Get all repositories for a specific owner.

        Args:
            owner: Repository owner name

        Returns:
            List of repositories
        """
        conn = await self.get_connection()
        try:
            rows = await conn.fetch(
                "SELECT * FROM repo WHERE owner = $1 ORDER BY stars DESC",
                owner,
            )
            return [dict(row) for row in rows]
        finally:
            await self.release_connection(conn)

    async def cleanup_old_stats(self, days_to_keep: int = 30) -> int:
        """Clean up old statistics records.

        Args:
            days_to_keep: Number of days of statistics to keep

        Returns:
            Number of records deleted
        """
        conn = await self.get_connection()
        try:
            cutoff_date = datetime.now(UTC).date()
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_to_keep)

            result = await conn.execute(
                "DELETE FROM repo_stats WHERE fetched_date < $1",
                cutoff_date,
            )

            count = int(result.split()[-1])
            self.logger.info(f"Cleaned up {count} old statistics records")
            return count

        finally:
            await self.release_connection(conn)

    async def __aenter__(self) -> "DatabaseRepository":
        """Async context manager entry."""
        if not self.pool:
            self.pool = await self.create_pool()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self.pool:
            await self.pool.close()
            self.pool = None
