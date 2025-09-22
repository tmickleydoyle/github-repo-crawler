"""Main entry point for the GitHub crawler application."""

import argparse
import asyncio

from .client import GitHubClient
from .config import get_settings
from .db_repository import DatabaseRepository
from .csv_tracker import CSVRepositoryTracker
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

            # Initialize CSV repository tracker for global deduplication
            csv_tracker = CSVRepositoryTracker()
            run_id = csv_tracker.generate_run_id(args.matrix_total, args.matrix_index)

            # Show CSV tracking stats
            csv_stats = csv_tracker.get_csv_stats()
            logger.info(
                "📊 CSV tracking stats",
                csv_exists=csv_stats["csv_exists"],
                total_repositories=csv_stats["total_repositories"],
                unique_runs=csv_stats["unique_run_ids"],
                latest_run=csv_stats["latest_run_id"],
                current_run_id=run_id
            )

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
                    csv_tracker=None,  # Temporarily disable CSV tracking
                )

                await db_repo.store_repositories(crawl_result, args.matrix_index)

                # Append new repositories to CSV with run tracking
                if crawl_result.repositories:
                    repo_data = []
                    for repo in crawl_result.repositories:
                        repo_data.append({
                            'id': repo.id,
                            'name': repo.name,
                            'name_with_owner': repo.name_with_owner,
                            'url': repo.url,
                            'created_at': repo.created_at,
                            'stars': repo.stars,
                            'forks': repo.forks,
                            'language': repo.language,
                            'owner': repo.owner,
                            'license': repo.license,
                            'pushed_at': repo.pushed_at,
                            'updated_at': repo.updated_at,
                        })

                    success = csv_tracker.append_repositories_to_csv(
                        repo_data, run_id, args.matrix_index
                    )

                    if success:
                        logger.info("Successfully appended repositories to CSV",
                                  count=len(repo_data), run_id=run_id)
                    else:
                        logger.error("Failed to append repositories to CSV")

                # Show updated stats
                final_csv_stats = csv_tracker.get_csv_stats()
                final_stats = await db_repo.get_discovery_stats()
                logger.info(
                    "📈 Final stats",
                    csv_total=final_csv_stats["total_repositories"],
                    postgres_total=final_stats["total_discovered"],
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
