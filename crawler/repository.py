import asyncpg
import asyncio
from datetime import date
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .models import Repo, RepoStats
from .config import settings

class RepoRepository:
    """
    Repository class for database operations on GitHub repositories and statistics.
    
    Handles database connections, retries, and CRUD operations for the core
    repo and repo_stats tables used by the GitHub crawler.
    """
    
    def __init__(self, dsn: str = settings.database_url):
        self.dsn = dsn
        self.pool = None

    async def init(self):
        """Initialize the database connection pool."""
        self.pool = await asyncpg.create_pool(
            self.dsn, 
            min_size=5, 
            max_size=20,
            command_timeout=60
        )

    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()

    @retry(
        retry=retry_if_exception_type((asyncpg.exceptions.ConnectionDoesNotExistError, 
                                     asyncpg.exceptions.InterfaceError,
                                     asyncpg.exceptions.PostgresError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3)
    )
    async def upsert_repos(self, repos: list[Repo]):
        """
        Insert or update repository records.
        
        Uses ON CONFLICT to handle duplicate repository IDs gracefully.
        Preserves existing alphabet_partition values when updating.
        """
        if not repos:
            return
            
        sql = """
        INSERT INTO repo (id, name, owner, url, created_at, alphabet_partition)
          VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO UPDATE SET
          name = EXCLUDED.name,
          owner = EXCLUDED.owner,
          url = EXCLUDED.url,
          created_at = EXCLUDED.created_at,
          alphabet_partition = COALESCE(EXCLUDED.alphabet_partition, repo.alphabet_partition)
        """
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(sql, [
                    (r.id, r.name, r.owner, r.url, r.created_at, r.alphabet_partition) 
                    for r in repos
                ])

    @retry(
        retry=retry_if_exception_type((asyncpg.exceptions.ConnectionDoesNotExistError, 
                                     asyncpg.exceptions.InterfaceError,
                                     asyncpg.exceptions.PostgresError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3)
    )
    async def insert_stats(self, stats: list[RepoStats]):
        """
        Insert or update repository statistics.
        
        Uses ON CONFLICT to handle duplicate (repo_id, fetched_date) pairs.
        Updates star counts for existing date records.
        """
        if not stats:
            return
            
        sql = """
        INSERT INTO repo_stats (repo_id, fetched_date, stars)
          VALUES ($1, $2, $3)
        ON CONFLICT (repo_id, fetched_date)
          DO UPDATE SET stars = EXCLUDED.stars
        """
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(sql, [
                    (s.repo_id, s.fetched_date, s.stars) 
                    for s in stats
                ])
