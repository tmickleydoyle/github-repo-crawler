#!/usr/bin/env python
"""Test script to debug the crawler issue."""

import asyncio
import os
import sys
from datetime import UTC, datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawler.client import GitHubClient
from crawler.config import get_settings
from crawler.db_repository import DatabaseRepository
from crawler.logger import setup_logging, get_logger


async def test_crawler():
    """Test the crawler with minimal configuration."""
    # Setup logging
    settings = get_settings()
    setup_logging(
        level="INFO",
        format_type="json",
        enable_colors=True,
        include_timestamp=True,
    )

    logger = get_logger(__name__)

    # Test with a very limited crawl
    matrix_index = 0
    matrix_total = 1

    logger.info("Starting test crawler", matrix_index=matrix_index, matrix_total=matrix_total)

    try:
        # Test GitHub client connection
        async with GitHubClient() as client:
            logger.info("Testing GitHub connection...")
            if not await client.test_connection():
                logger.error("GitHub API connection test failed")
                return

            logger.info("GitHub connection successful, starting crawl...")

            # Crawl with very limited scope
            crawl_result = await client.crawl(
                matrix_total=matrix_total,
                matrix_index=matrix_index
            )

            logger.info(
                "Crawl completed",
                repositories_found=len(crawl_result.repositories),
                total_stars=crawl_result.total_stars,
                unique_owners=crawl_result.unique_owners
            )

            if not crawl_result.repositories:
                logger.warning("No repositories found in crawl result!")
                return

            # Store in database
            logger.info("Storing repositories in database...")
            async with DatabaseRepository() as db_repo:
                await db_repo.initialize_schema()

                logger.info(
                    "About to store repositories",
                    count=len(crawl_result.repositories)
                )

                # Log first few repositories for debugging
                for i, repo in enumerate(crawl_result.repositories[:3]):
                    logger.info(
                        f"Sample repo {i+1}",
                        id=repo.id,
                        name=repo.name,
                        owner=repo.owner,
                        stars=repo.stars,
                        url=repo.url
                    )

                storage_result = await db_repo.store_repositories(
                    crawl_result, matrix_index
                )

                logger.info(
                    "Storage completed",
                    successful=storage_result["successful"],
                    failed=storage_result["failed"],
                    total=storage_result["total"]
                )

                # Verify data was stored
                total_count = await db_repo.get_total_repository_count()
                logger.info(f"Total repositories in database: {total_count}")

                if total_count == 0:
                    logger.error("No repositories in database after storage!")
                else:
                    logger.info(f"Success! {total_count} repositories stored in database")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Set environment variables for database connection
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PORT", "5432")
    os.environ.setdefault("POSTGRES_DB", "crawler")
    os.environ.setdefault("POSTGRES_USER", "postgres")
    os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
    os.environ.setdefault("MAX_REPOS", "10")  # Test with just 10 repos

    asyncio.run(test_crawler())