"""Supabase tracking database for repository deduplication."""

import asyncio
from typing import Set, List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncpg
import structlog

from .config import get_settings

logger = structlog.get_logger(__name__)


class RepositoryTracker:
    """Manages tracking of scraped repositories in Supabase for deduplication."""

    def __init__(self):
        self.settings = get_settings()
        self._pool: Optional[asyncpg.Pool] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def initialize(self):
        """Initialize connection pool and database schema."""
        if not self.settings.external_database_url:
            logger.warning("No DATABASE_URL provided - repository tracking disabled")
            return

        try:
            # Create connection pool
            self._pool = await asyncpg.create_pool(
                self.settings.external_database_url,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )

            # Initialize schema
            await self._initialize_schema()
            logger.info("Repository tracker initialized with Supabase")

        except Exception as e:
            logger.error("Failed to initialize repository tracker", error=str(e))
            self._pool = None

    async def close(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def _initialize_schema(self):
        """Create necessary tables for tracking."""
        if not self._pool:
            return

        async with self._pool.acquire() as conn:
            # Table to track discovered repositories
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS discovered_repositories (
                    repo_id BIGINT PRIMARY KEY,
                    first_discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    times_discovered INTEGER DEFAULT 1,
                    matrix_index INTEGER,
                    crawl_run_id TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)

            # Table to track detailed repository data
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS repo_tracking (
                    id BIGINT PRIMARY KEY,
                    name_with_owner TEXT NOT NULL,
                    url TEXT NOT NULL,
                    stars INTEGER DEFAULT 0,
                    forks INTEGER DEFAULT 0,
                    language TEXT,
                    created_at TIMESTAMP WITH TIME ZONE,
                    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    data_fetched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)

            # Create indexes for performance
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_discovered_last_seen
                ON discovered_repositories (last_seen_at);
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_discovered_crawl_run
                ON discovered_repositories (crawl_run_id);
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_repo_tracking_name
                ON repo_tracking (name_with_owner);
            """)

    async def get_recently_discovered(self, hours: int = 24) -> Set[int]:
        """Get repository IDs discovered within the last N hours."""
        if not self._pool:
            return set()

        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT repo_id
                    FROM discovered_repositories
                    WHERE last_seen_at > $1
                """, cutoff_time)

                discovered_ids = {row['repo_id'] for row in rows}
                logger.info("Retrieved recently discovered repositories",
                          count=len(discovered_ids), hours=hours)
                return discovered_ids

        except Exception as e:
            logger.error("Failed to get recently discovered repos", error=str(e))
            return set()

    async def mark_repositories_discovered(
        self,
        repo_ids: List[int],
        matrix_index: int,
        crawl_run_id: str
    ) -> List[int]:
        """Mark repositories as discovered and return new discoveries."""
        if not self._pool or not repo_ids:
            return repo_ids

        try:
            new_discoveries = []

            async with self._pool.acquire() as conn:
                for repo_id in repo_ids:
                    # Insert or update discovered repository
                    result = await conn.fetchrow("""
                        INSERT INTO discovered_repositories
                        (repo_id, matrix_index, crawl_run_id, last_seen_at, times_discovered)
                        VALUES ($1, $2, $3, NOW(), 1)
                        ON CONFLICT (repo_id)
                        DO UPDATE SET
                            last_seen_at = NOW(),
                            times_discovered = discovered_repositories.times_discovered + 1,
                            matrix_index = $2,
                            crawl_run_id = $3
                        RETURNING first_discovered_at = last_seen_at as is_new
                    """, repo_id, matrix_index, crawl_run_id)

                    # Track if this is a new discovery
                    if result and result['is_new']:
                        new_discoveries.append(repo_id)

                logger.info("Marked repositories as discovered",
                          total=len(repo_ids), new=len(new_discoveries),
                          matrix_index=matrix_index)

                return new_discoveries

        except Exception as e:
            logger.error("Failed to mark repositories as discovered", error=str(e))
            return repo_ids  # Return all as "new" if tracking fails

    async def store_repository_data(self, repositories: List[Dict[str, Any]]):
        """Store detailed repository data for aggregation."""
        if not self._pool or not repositories:
            return

        try:
            async with self._pool.acquire() as conn:
                # Prepare data for bulk insert
                repo_data = []
                for repo in repositories:
                    repo_data.append((
                        repo.get('id'),
                        repo.get('name_with_owner'),
                        repo.get('url'),
                        repo.get('stars', 0),
                        repo.get('forks', 0),
                        repo.get('language'),
                        repo.get('created_at'),
                    ))

                # Bulk insert with conflict resolution
                await conn.executemany("""
                    INSERT INTO repo_tracking
                    (id, name_with_owner, url, stars, forks, language, created_at, data_fetched_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    ON CONFLICT (id)
                    DO UPDATE SET
                        stars = EXCLUDED.stars,
                        forks = EXCLUDED.forks,
                        language = EXCLUDED.language,
                        last_updated = NOW(),
                        data_fetched_at = NOW()
                """, repo_data)

                logger.info("Stored repository data in tracking database",
                          count=len(repositories))

        except Exception as e:
            logger.error("Failed to store repository data", error=str(e))

    async def get_tracking_stats(self) -> Dict[str, Any]:
        """Get statistics about tracked repositories."""
        if not self._pool:
            return {"tracking_enabled": False}

        try:
            async with self._pool.acquire() as conn:
                # Get discovery stats
                discovered_stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_discovered,
                        COUNT(*) FILTER (WHERE last_seen_at > NOW() - INTERVAL '24 hours') as discovered_last_24h,
                        COUNT(*) FILTER (WHERE last_seen_at > NOW() - INTERVAL '1 hour') as discovered_last_hour
                    FROM discovered_repositories
                """)

                # Get repository data stats
                repo_stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_tracked,
                        AVG(stars) as avg_stars,
                        MAX(stars) as max_stars,
                        COUNT(DISTINCT language) as unique_languages
                    FROM repo_tracking
                """)

                return {
                    "tracking_enabled": True,
                    "total_discovered": discovered_stats['total_discovered'],
                    "discovered_last_24h": discovered_stats['discovered_last_24h'],
                    "discovered_last_hour": discovered_stats['discovered_last_hour'],
                    "total_tracked": repo_stats['total_tracked'],
                    "avg_stars": float(repo_stats['avg_stars']) if repo_stats['avg_stars'] else 0,
                    "max_stars": repo_stats['max_stars'],
                    "unique_languages": repo_stats['unique_languages'],
                }

        except Exception as e:
            logger.error("Failed to get tracking stats", error=str(e))
            return {"tracking_enabled": True, "error": str(e)}

    async def get_repository_data(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get stored repository data for aggregation."""
        if not self._pool:
            return []

        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT rt.*, dr.first_discovered_at, dr.times_discovered
                    FROM repo_tracking rt
                    JOIN discovered_repositories dr ON rt.id = dr.repo_id
                    ORDER BY rt.stars DESC, rt.id
                """

                if limit:
                    query += f" LIMIT {limit}"

                rows = await conn.fetch(query)

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error("Failed to get repository data", error=str(e))
            return []