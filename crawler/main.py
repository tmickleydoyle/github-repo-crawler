"""Main entry point for the GitHub crawler application."""

import argparse
import asyncio

from .client import GitHubClient
from .config import get_settings
from .db_repository import DatabaseRepository
from .logger import get_logger, setup_logging


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    settings = get_settings()
    p = argparse.ArgumentParser(description="Crawl GitHub repos for star counts")
    p.add_argument(
        "--repos",
        type=int,
        default=settings.crawler_max_repos,
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


async def run() -> None:
    """
    Main entry point using clean architecture principles.

    This function demonstrates proper:
    - Resource management with async context managers
    - Error handling with custom exceptions
    - Domain model usage
    - Separation of concerns
    - Centralized database operations
    """
    args = parse_args()
    settings = get_settings()

    # Setup structured logging (CLAUDE.md: "Use structured logging")
    setup_logging(
        level=settings.log_level,
        format_type=settings.log_format,
        enable_colors=settings.log_enable_colors,
        include_timestamp=settings.log_include_timestamp,
    )

    logger = get_logger(
        __name__,
        environment=settings.environment,
        matrix_index=args.matrix_index,
        matrix_total=args.matrix_total,
    )

    logger.info(
        "Starting GitHub crawler",
        target_repos=args.repos,
        matrix_job=f"{args.matrix_index + 1}/{args.matrix_total}",
    )

    try:
        async with GitHubClient() as client:
            if not await client.test_connection():
                logger.error("GitHub API connection test failed")
                return

            crawl_result = await client.crawl(
                matrix_total=args.matrix_total,
                matrix_index=args.matrix_index,
                target_repos=args.repos,
            )

            # Use centralized database repository (CLAUDE.md: "Centralization")
            async with DatabaseRepository() as db_repo:
                await db_repo.initialize_schema()
                await db_repo.store_repositories(crawl_result, args.matrix_index)

            logger.info(
                "Crawl completed successfully",
                repositories_count=len(crawl_result.repositories),
            )

    except Exception as e:
        logger.error(
            "Crawl failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


def main() -> None:
    """Main entry point."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
