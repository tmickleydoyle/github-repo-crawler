import asyncpg
import asyncio
from datetime import date
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .models import Repo, RepoStats, RepoArchive, RepoFileIndex
from .config import settings

class RepoRepository:
    def __init__(self, dsn: str = settings.database_url):
        self.dsn = dsn
        self.pool = None

    async def init(self):
        # Increase pool size for matrix scenarios with many concurrent connections
        self.pool = await asyncpg.create_pool(
            self.dsn, 
            min_size=5, 
            max_size=20,
            command_timeout=60
        )

    async def close(self):
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
        if not repos:
            return
        sql = """
        INSERT INTO repo (id, name, owner, url, created_at, alphabet_partition)
          VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO UPDATE SET
          alphabet_partition = COALESCE(EXCLUDED.alphabet_partition, repo.alphabet_partition)
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Batch insert using executemany for better performance
                await conn.executemany(sql, [(r.id, r.name, r.owner, r.url, r.created_at, r.alphabet_partition) for r in repos])

    @retry(
        retry=retry_if_exception_type((asyncpg.exceptions.ConnectionDoesNotExistError, 
                                     asyncpg.exceptions.InterfaceError,
                                     asyncpg.exceptions.PostgresError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3)
    )
    async def insert_stats(self, stats: list[RepoStats]):
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
                # Batch insert using executemany for better performance
                await conn.executemany(sql, [(s.repo_id, s.fetched_date, s.stars) for s in stats])

    async def insert_archive(self, archive: RepoArchive):
        sql = """
        INSERT INTO repo_archives (repo_id, fetched_date, archive_path)
          VALUES ($1, $2, $3)
        ON CONFLICT (repo_id, fetched_date) DO NOTHING
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, archive.repo_id, archive.fetched_date, archive.archive_path)

    async def upsert_file_index(self, indexes: list[RepoFileIndex]):
        if not indexes:
            return
        sql = """
        INSERT INTO repo_file_index (repo_id, fetched_date, path, content_sha)
          VALUES ($1, $2, $3, $4)
        ON CONFLICT (repo_id, fetched_date, path)
          DO UPDATE SET content_sha = EXCLUDED.content_sha
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Batch insert using executemany for better performance
                await conn.executemany(sql, [(idx.repo_id, idx.fetched_date, idx.path, idx.content_sha) for idx in indexes])
