import asyncpg
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import settings
from .models import Repo, RepoStats


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
            self.dsn, min_size=5, max_size=20, command_timeout=60
        )

    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()

    @retry(
        retry=retry_if_exception_type(
            (
                asyncpg.exceptions.ConnectionDoesNotExistError,
                asyncpg.exceptions.InterfaceError,
                asyncpg.exceptions.PostgresError,
            )
        ),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def upsert_repos(self, repos: list[Repo]):
        """
        Insert or update repository records with comprehensive metadata.

        Uses ON CONFLICT to handle duplicate repository IDs gracefully.
        Preserves existing alphabet_partition values when updating.
        The name_with_owner field is automatically populated by database trigger.
        """
        if not repos:
            return

        sql = """
        INSERT INTO repo (
            id, name, owner, url, created_at, alphabet_partition,
            description, homepage_url, topics, languages,
            watchers_count, open_issues_count, subscribers_count,
            network_count, size_kb,
            default_branch, visibility, license_name, primary_language,
            is_fork, is_archived, is_disabled, is_template,
            has_issues, has_projects, has_wiki, has_pages, has_downloads,
            pushed_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6,
            $7, $8, $9, $10,
            $11, $12, $13, $14, $15,
            $16, $17, $18, $19,
            $20, $21, $22, $23,
            $24, $25, $26, $27, $28,
            $29, $30
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            owner = EXCLUDED.owner,
            url = EXCLUDED.url,
            created_at = EXCLUDED.created_at,
            alphabet_partition = COALESCE(EXCLUDED.alphabet_partition,
                                       repo.alphabet_partition),
            description = EXCLUDED.description,
            homepage_url = EXCLUDED.homepage_url,
            topics = EXCLUDED.topics,
            languages = EXCLUDED.languages,
            watchers_count = EXCLUDED.watchers_count,
            open_issues_count = EXCLUDED.open_issues_count,
            subscribers_count = EXCLUDED.subscribers_count,
            network_count = EXCLUDED.network_count,
            size_kb = EXCLUDED.size_kb,
            default_branch = EXCLUDED.default_branch,
            visibility = EXCLUDED.visibility,
            license_name = EXCLUDED.license_name,
            primary_language = EXCLUDED.primary_language,
            is_fork = EXCLUDED.is_fork,
            is_archived = EXCLUDED.is_archived,
            is_disabled = EXCLUDED.is_disabled,
            is_template = EXCLUDED.is_template,
            has_issues = EXCLUDED.has_issues,
            has_projects = EXCLUDED.has_projects,
            has_wiki = EXCLUDED.has_wiki,
            has_pages = EXCLUDED.has_pages,
            has_downloads = EXCLUDED.has_downloads,
            pushed_at = EXCLUDED.pushed_at,
            updated_at = EXCLUDED.updated_at
        """

        if not self.pool:
            raise RuntimeError("Repository not initialized. Call init() first.")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(
                    sql,
                    [
                        (
                            # Core fields ($1-$6)
                            r.id,
                            r.name,
                            r.owner,
                            r.url,
                            r.created_at,
                            r.alphabet_partition,
                            # Content fields ($7-$10)
                            r.description,
                            r.homepage_url,
                            r.topics,
                            r.languages,
                            # Statistics fields ($11-$15)
                            r.watchers_count,
                            r.open_issues_count,
                            r.subscribers_count,
                            r.network_count,
                            r.size_kb,
                            # Configuration fields ($16-$19)
                            r.default_branch,
                            r.visibility,
                            r.license_name,
                            r.primary_language,
                            # State flags ($20-$23)
                            r.is_fork,
                            r.is_archived,
                            r.is_disabled,
                            r.is_template,
                            # Feature flags ($24-$28)
                            r.has_issues,
                            r.has_projects,
                            r.has_wiki,
                            r.has_pages,
                            r.has_downloads,
                            # Timestamp fields ($29-$30)
                            r.pushed_at,
                            r.updated_at,
                        )
                        for r in repos
                    ],
                )

    @retry(
        retry=retry_if_exception_type(
            (
                asyncpg.exceptions.ConnectionDoesNotExistError,
                asyncpg.exceptions.InterfaceError,
                asyncpg.exceptions.PostgresError,
            )
        ),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
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

        if not self.pool:
            raise RuntimeError("Repository not initialized. Call init() first.")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(
                    sql, [(s.repo_id, s.fetched_date, s.stars) for s in stats]
                )
