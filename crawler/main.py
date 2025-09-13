import argparse
import asyncio
import logging
from datetime import datetime, timezone

from .client import GitHubClient
from .config import settings
from .domain import CrawlResult, Repository, create_repository_stats
from .repository import RepoRepository
from .memory_utils import MemoryEfficientProcessor, memory_management

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)



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
    Store repositories using the repository layer with enhanced error handling
    and memory-efficient processing.

    This function implements proper database operations with:
    - Repository pattern usage
    - Comprehensive error handling  
    - Transaction safety
    - Bulk operations for performance
    - Memory-efficient batch processing
    """
    repo_repository = RepoRepository()
    
    try:
        await repo_repository.init()
        
        current_date = datetime.now(timezone.utc).date()
        
        # Use memory-efficient processing for large datasets
        with memory_management(force_gc=True, threshold_mb=50):
            processor = MemoryEfficientProcessor(chunk_size=500, max_memory_mb=256)
            
            def process_chunk(repositories_chunk):
                """Process a chunk of repositories."""
                from .domain import repository_to_repo_model, repository_to_repo_stats_model
                
                repos = []
                stats = []
                
                for repository in repositories_chunk:
                    try:
                        # Create repo model with matrix partition
                        repo_model = repository_to_repo_model(
                            repository, 
                            alphabet_partition=f"matrix_{matrix_index}"
                        )
                        repos.append(repo_model)
                        
                        # Create stats model
                        stats_model = repository_to_repo_stats_model(repository, current_date)
                        stats.append(stats_model)
                        
                    except Exception as e:
                        logger.error(f"⚠️ Error converting repo {repository.id}: {e}")
                        continue
                
                return repos, stats
            
            # Process repositories in memory-efficient chunks
            all_repos = []
            all_stats = []
            
            from .memory_utils import chunk_list
            for chunk in chunk_list(crawl_result.repositories, processor.chunk_size):
                try:
                    repos, stats = process_chunk(chunk)
                    all_repos.extend(repos)
                    all_stats.extend(stats)
                except Exception as e:
                    logger.error(f"⚠️ Error processing chunk: {e}")
                    continue
        
        # Bulk insert operations
        if all_repos:
            await repo_repository.upsert_repos(all_repos)
        if all_stats:
            await repo_repository.insert_stats(all_stats)
        
        logger.info(f"✅ Successfully stored {len(all_repos)} repositories")
        
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
        await repo_repository.close()


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
