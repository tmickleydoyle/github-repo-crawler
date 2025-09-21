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
    p.add_argument(
        "--report-only",
        action="store_true",
        help="Generate crawling report without running crawler",
    )
    return p.parse_args()


async def generate_report() -> None:
    """Generate and display crawling report."""
    settings = get_settings()
    from .rate_limit_scheduler import RateLimitScheduler

    setup_logging(
        level=settings.log_level,
        format_type=settings.log_format,
        enable_colors=settings.log_enable_colors,
        include_timestamp=settings.log_include_timestamp,
    )

    logger = get_logger(__name__, environment=settings.environment)

    logger.info("📊 Generating crawling report...")

    async with GitHubClient() as client:
        report = await client.get_crawling_report()

        if "error" in report:
            logger.error(f"❌ {report['error']}")
            logger.info(f"💡 {report['recommendation']}")
            return

        logger.info("=" * 60)
        logger.info("GITHUB CRAWLER REPORT")
        logger.info("=" * 60)

        # Summary
        summary = report["summary"]
        logger.info(f"Total Unique Repositories: {summary['total_unique_repositories']:,}")
        logger.info(f"Total Repositories Seen: {summary['total_repositories_seen']:,}")
        logger.info(f"Completion: {summary['completion_percentage']}%")
        logger.info(f"Estimated Total: {summary['estimated_total']:,}")

        # Partitions
        partitions = report["partitions"]
        logger.info("")
        logger.info("PARTITION STATUS:")
        logger.info(f"  Total: {partitions['total']:,}")
        logger.info(f"  Pending: {partitions['pending']:,}")
        logger.info(f"  In Progress: {partitions['in_progress']:,}")
        logger.info(f"  Completed: {partitions['completed']:,}")
        logger.info(f"  Exhausted: {partitions['exhausted']:,}")

        # Performance
        perf = report["performance"]
        logger.info("")
        logger.info("PERFORMANCE:")
        logger.info(f"  Workflow Runs: {perf['workflow_runs']}")
        logger.info(f"  Avg Repos/Partition: {perf['avg_repos_per_partition']}")
        logger.info(f"  Est. Runs Remaining: {perf['estimated_runs_remaining']}")

        # Recommendations
        rec = report["recommendations"]
        logger.info("")
        logger.info("RECOMMENDATIONS:")
        logger.info(f"  Next Matrix Size: {rec['next_matrix_size']}")
        if rec['gist_id']:
            logger.info(f"  State Gist ID: {rec['gist_id']}")
        else:
            logger.info("  ⚠️ No Gist ID configured - state will not persist!")
            logger.info("  Add CRAWLER_STATE_GIST_ID to your repository secrets")

        # Rate limit recommendations
        scheduler = RateLimitScheduler()
        if partitions['pending'] > 0:
            config = scheduler.suggest_workflow_config(partitions['pending'])
            logger.info("")
            logger.info("NEXT RUN CONFIGURATION:")
            logger.info(f"  Matrix Size: {config['matrix_size']}")
            logger.info(f"  Max Repos per Job: {config['max_repos_per_job']}")
            logger.info(f"  Frequency: {config['frequency']}")

        logger.info("=" * 60)


async def run() -> None:
    """
    Main entry point with state management support.

    This function demonstrates proper:
    - Resource management with async context managers
    - Error handling with custom exceptions
    - State management for deduplication
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

    # Report mode
    if args.report_only:
        await generate_report()
        return

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
        stateful=settings.crawler_use_stateful_strategy,
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
