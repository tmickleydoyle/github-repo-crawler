"""Main entry point for the GitHub crawler application."""

import argparse
import asyncio
import sys
from typing import Any

from .client import GitHubClient
from .config import get_settings
from .csv_deduplication import CSVDeduplicator
from .db_repository import DatabaseRepository
from .domain import RateLimitExhaustedError
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
    p.add_argument(
        "--consolidate-only",
        action="store_true",
        help="Only perform consolidation of matrix job results (no crawling)",
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

    # Check if this is a consolidation-only run
    if args.consolidate_only:
        logger.info(
            "Starting matrix job consolidation",
            matrix_total=args.matrix_total,
        )
        await run_consolidation(args, logger)
        return

    logger.info(
        "Starting GitHub crawler",
        target_repos=args.repos,
        matrix_job=f"{args.matrix_index + 1}/{args.matrix_total}",
    )

    try:
        # Use centralized database repository (CLAUDE.md: "Centralization")
        try:
            async with DatabaseRepository() as db_repo:
                await run_with_database(db_repo, args, logger)
        except Exception as db_error:
            logger.warning(
                "Database connection failed, running without persistence",
                error=str(db_error),
            )
            await run_without_database(args, logger)

    except RateLimitExhaustedError as e:
        logger.warning(
            "Crawler stopped gracefully due to API rate limit exhaustion",
            error=str(e),
        )
        sys.exit(0)
    except Exception as e:
        logger.error(
            "Crawl failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


async def run_with_database(db_repo: Any, args: Any, logger: Any) -> None:
    """Run crawler with database persistence."""
    await db_repo.initialize_schema()

    # Create CSV deduplicator for additional filtering (matrix-specific file)
    csv_deduplicator = CSVDeduplicator(matrix_index=args.matrix_index)
    csv_stats = csv_deduplicator.get_stats()
    logger.info(
        "CSV deduplication initialized",
        csv_exists=csv_stats["csv_exists"],
        known_repos=csv_stats["total_repositories"],
    )

    # Show discovery stats from previous runs
    discovery_stats = await db_repo.get_discovery_stats()
    if discovery_stats["total_discovered"] > 0:
        logger.info(
            "📊 Previous discovery stats",
            total_discovered=discovery_stats["total_discovered"],
            discovered_last_24h=discovery_stats["discovered_last_24h"],
            rediscovered_count=discovery_stats["rediscovered_repos"],
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
                db_repository=db_repo,
                csv_deduplicator=csv_deduplicator,
            )

            await db_repo.store_repositories(crawl_result, args.matrix_index)

            run_id = f"run-{args.matrix_index}-db"
            csv_deduplicator.export_repositories_to_csv(
                crawl_result.repositories, run_id, args.matrix_index
            )

            final_stats = await db_repo.get_discovery_stats()
            logger.info(
                "📈 Final discovery stats",
                total_discovered=final_stats["total_discovered"],
                new_this_run=final_stats["total_discovered"]
                - discovery_stats["total_discovered"],
            )

        logger.info(
            "Crawl completed successfully",
            repositories_count=len(crawl_result.repositories),
        )

    except RateLimitExhaustedError as e:
        logger.warning(
            "Rate limit exhausted - saving partial results",
            error=str(e),
        )
        raise


async def run_without_database(args: Any, logger: Any) -> None:
    """Run crawler without database persistence (fallback mode)."""
    logger.info("Running in fallback mode without database persistence")

    csv_deduplicator = CSVDeduplicator(matrix_index=args.matrix_index)
    csv_stats = csv_deduplicator.get_stats()
    logger.info(
        "CSV deduplication initialized",
        csv_exists=csv_stats["csv_exists"],
        known_repos=csv_stats["total_repositories"],
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
                db_repository=None,
                csv_deduplicator=csv_deduplicator,
            )

            run_id = f"run-{args.matrix_index}-fallback"
            csv_deduplicator.export_repositories_to_csv(
                crawl_result.repositories, run_id, args.matrix_index
            )

            logger.info(
                "Crawl completed successfully (CSV persistence)",
                repositories_count=len(crawl_result.repositories),
            )

    except RateLimitExhaustedError as e:
        logger.warning(
            "Rate limit exhausted - saving partial results",
            error=str(e),
        )
        raise


async def run_consolidation(args: Any, logger: Any) -> None:
    """Run consolidation of matrix job results into single hour file."""
    from .csv_deduplication import CSVDeduplicator

    success = CSVDeduplicator.consolidate_matrix_results(matrix_total=args.matrix_total)

    if success:
        logger.info(
            "Matrix job consolidation completed successfully",
            matrix_total=args.matrix_total,
        )
    else:
        logger.error(
            "Matrix job consolidation failed",
            matrix_total=args.matrix_total,
        )
        raise RuntimeError("Consolidation failed")


def main() -> None:
    """Main entry point."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
