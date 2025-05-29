import argparse
import asyncio
import asyncpg
import os
import logging
from datetime import datetime, timezone

from .client import GitHubClient
from .config import settings
from .domain import CrawlResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_github_datetime(dt_input):
    """
    Parse GitHub datetime string or datetime object to timezone-naive datetime for PostgreSQL
    """
    if not dt_input:
        return None
    
    if isinstance(dt_input, datetime):
        if dt_input.tzinfo:
            return dt_input.astimezone(timezone.utc).replace(tzinfo=None)
        return dt_input
    
    if isinstance(dt_input, str):
        dt_aware = datetime.fromisoformat(dt_input.replace("Z", "+00:00"))
        return dt_aware.astimezone(timezone.utc).replace(tzinfo=None)
    
    return None


def parse_args():
    p = argparse.ArgumentParser(description="Crawl GitHub repos for star counts")
    p.add_argument(
        "--repos",
        type=int,
        default=settings.max_repos,
        help="Number of repos to crawl",
    )
    p.add_argument(
        "--matrix-total",
        type=int,
        default=1,
        help="Total number of matrix jobs",
    )
    p.add_argument(
        "--matrix-index",
        type=int,
        default=0,
        help="Current matrix job index (0-based)",
    )
    return p.parse_args()


async def store_repositories(crawl_result: CrawlResult, matrix_index: int):
    """
    Store repositories using domain models with enhanced error handling.

    This function implements proper database operations with:
    - Domain model usage instead of raw dictionaries
    - Comprehensive error handling
    - Transaction safety
    - Proper connection management
    """
    conn = None
    try:
        conn = await asyncpg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            database=os.getenv("POSTGRES_DB", "crawler"),
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS repo (
                id BIGINT PRIMARY KEY,
                name TEXT NOT NULL,
                owner TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at TIMESTAMP,
                alphabet_partition VARCHAR(100),
                name_with_owner TEXT
            )
        """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS repo_stats (
                repo_id BIGINT NOT NULL REFERENCES repo(id) ON DELETE CASCADE,
                fetched_date DATE NOT NULL,
                stars INT NOT NULL,
                PRIMARY KEY(repo_id, fetched_date)
            )
        """
        )

        await conn.execute("CREATE INDEX IF NOT EXISTS idx_repo_stars ON repo (id)")
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_repo_name_with_owner "
            "ON repo (name_with_owner)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_repo_alphabet_partition "
            "ON repo (alphabet_partition)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_repo_stats_date "
            "ON repo_stats (fetched_date)"
        )

        current_date = datetime.now(timezone.utc).date()

        async with conn.transaction():
            successful_inserts = 0
            failed_inserts = 0

            for repo in crawl_result.repositories:
                try:
                    # Parse datetime fields safely
                    created_at = parse_github_datetime(repo.created_at)

                    await conn.execute(
                        """
                        INSERT INTO repo
                        (id, name, owner, url, created_at, name_with_owner,
                         alphabet_partition)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (id) DO UPDATE SET
                            name_with_owner = EXCLUDED.name_with_owner,
                            alphabet_partition = EXCLUDED.alphabet_partition
                    """,
                        repo.id,
                        repo.name,
                        repo.owner,
                        repo.url,
                        created_at,
                        repo.name_with_owner,
                        f"matrix_{matrix_index}",
                    )

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

                    successful_inserts += 1

                except Exception as e:
                    logger.error(f"⚠️ Error inserting repo {repo.id}: {e}")
                    failed_inserts += 1

        logger.info(f"✅ Successfully stored {successful_inserts} repositories")
        if failed_inserts > 0:
            logger.warning(f"⚠️ Failed to store {failed_inserts} repositories")

        logger.info("📊 Crawl Statistics:")
        logger.info(f"   - Total repositories: {len(crawl_result.repositories)}")
        logger.info(f"   - Unique owners: {crawl_result.unique_owners}")
        logger.info(f"   - Total stars: {crawl_result.total_stars:,}")
        logger.info(f"   - Average stars: {crawl_result.average_stars:.1f}")
        logger.info(f"   - Matrix job: {matrix_index}")

    except Exception as e:
        logger.error(f"❌ Database operation failed: {e}")
        raise
    finally:
        if conn:
            await conn.close()


async def run():
    """
    Main entry point using clean architecture principles.

    This function demonstrates proper:
    - Resource management with async context managers
    - Error handling with custom exceptions
    - Domain model usage
    - Separation of concerns
    """
    args = parse_args()

    logger.info("🚀 Starting GitHub crawler")
    logger.info(f"📊 Target repositories: {args.repos}")
    logger.info(f"🔢 Matrix job: {args.matrix_index + 1}/{args.matrix_total}")

    try:
        async with GitHubClient() as client:
            if not await client.test_connection():
                logger.error("❌ GitHub API connection test failed")
                return

            crawl_result = await client.crawl(
                matrix_total=args.matrix_total, matrix_index=args.matrix_index
            )

            await store_repositories(crawl_result, args.matrix_index)

            logger.info("🎉 Crawl completed successfully!")

    except Exception as e:
        logger.error(f"❌ Crawl failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run())
