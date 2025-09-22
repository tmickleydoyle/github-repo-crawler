"""Main entry point for the GitHub crawler application."""

import argparse
import asyncio

from .client import GitHubClient
from .config import get_settings
from .db_repository import DatabaseRepository
from .tracking_db import RepositoryTracker
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
        # Use centralized database repository (CLAUDE.md: "Centralization")
        async with DatabaseRepository() as db_repo:
            await db_repo.initialize_schema()

            # Initialize Supabase repository tracker for global deduplication
            async with RepositoryTracker() as tracker:
                # Show current tracking stats
                tracking_stats = await tracker.get_tracking_stats()
                if tracking_stats.get("tracking_enabled"):
                    logger.info(
                        "📊 Supabase tracking stats",
                        total_discovered=tracking_stats["total_discovered"],
                        discovered_last_24h=tracking_stats["discovered_last_24h"],
                        total_tracked=tracking_stats["total_tracked"],
                        avg_stars=tracking_stats.get("avg_stars", 0)
                    )
                else:
                    logger.warning("Supabase tracking not available - running without global deduplication")

                # Show PostgreSQL discovery stats
                discovery_stats = await db_repo.get_discovery_stats()
                if discovery_stats["total_discovered"] > 0:
                    logger.info(
                        "📊 PostgreSQL persistence stats",
                        total_discovered=discovery_stats["total_discovered"],
                        discovered_last_24h=discovery_stats["discovered_last_24h"],
                        rediscovered_count=discovery_stats["rediscovered_repos"]
                    )

                async with GitHubClient() as client:
                    if not await client.test_connection():
                        logger.error("GitHub API connection test failed")
                        return

                    crawl_result = await client.crawl(
                        matrix_total=args.matrix_total,
                        matrix_index=args.matrix_index,
                        target_repos=args.repos,
                        db_repository=db_repo,  # PostgreSQL for local storage
                        repository_tracker=tracker,  # Supabase for global tracking
                    )

                    await db_repo.store_repositories(crawl_result, args.matrix_index)

                    # Show updated stats
                    final_tracking_stats = await tracker.get_tracking_stats()
                    if final_tracking_stats.get("tracking_enabled"):
                        logger.info(
                            "📈 Final tracking stats",
                            total_discovered=final_tracking_stats["total_discovered"],
                            total_tracked=final_tracking_stats["total_tracked"]
                        )

                    final_stats = await db_repo.get_discovery_stats()
                    logger.info(
                        "📈 Final PostgreSQL stats",
                        total_discovered=final_stats["total_discovered"],
                        new_this_run=final_stats["total_discovered"] - discovery_stats["total_discovered"]
                    )

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
