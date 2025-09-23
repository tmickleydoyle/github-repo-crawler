#!/usr/bin/env python3
"""Test the storage pipeline end-to-end to debug Supabase issues."""

import asyncio
import os
import sys

# Use environment variable
if not os.environ.get("DATABASE_URL"):
    print("❌ DATABASE_URL environment variable not set")
    print("Set it with: export DATABASE_URL='your_connection_string'")
    sys.exit(1)

from crawler.client import GitHubClient
from crawler.db_repository import DatabaseRepository


async def test_storage_pipeline():
    """Test the complete storage pipeline with a small batch."""
    print("🧪 Testing Storage Pipeline End-to-End")
    print("=" * 60)

    # Test with a very small batch
    target_repos = 5
    matrix_index = 999  # Use unique matrix index for testing

    try:
        async with DatabaseRepository() as db_repo:
            print("✅ Database connection established")

            # Initialize schema
            await db_repo.initialize_schema()
            print("✅ Schema initialized")

            # Check initial counts
            conn = await db_repo.get_connection()
            try:
                initial_repo_count = await conn.fetchval("SELECT COUNT(*) FROM repo")
                initial_discovered_count = await conn.fetchval("SELECT COUNT(*) FROM discovered_repositories")
                print(f"📊 Initial counts - repo: {initial_repo_count}, discovered: {initial_discovered_count}")
            finally:
                await db_repo.release_connection(conn)

            async with GitHubClient() as client:
                print("✅ GitHub client initialized")

                # Test connection
                if not await client.test_connection():
                    print("❌ GitHub API connection failed")
                    return
                print("✅ GitHub API connection successful")

                # Run a small crawl
                print(f"\n🚀 Starting test crawl (target: {target_repos} repos)")
                result = await client.crawl(
                    matrix_total=1000,  # Large number so we get unique queries
                    matrix_index=matrix_index,
                    target_repos=target_repos,
                    db_repository=db_repo
                )

                print(f"🔍 Crawl completed - found {len(result.repositories)} repositories")

                if result.repositories:
                    print("📋 Sample repositories found:")
                    for i, repo in enumerate(result.repositories[:3]):
                        print(f"  {i+1}. {repo.name_with_owner} (ID: {repo.id}, Stars: {repo.stars})")

                    # Store the repositories
                    print(f"\n💾 Storing {len(result.repositories)} repositories...")
                    storage_result = await db_repo.store_repositories(result, matrix_index)
                    print(f"📊 Storage result: {storage_result}")

                    # Check final counts
                    conn = await db_repo.get_connection()
                    try:
                        final_repo_count = await conn.fetchval("SELECT COUNT(*) FROM repo")
                        final_discovered_count = await conn.fetchval("SELECT COUNT(*) FROM discovered_repositories")

                        repo_increase = final_repo_count - initial_repo_count
                        discovered_increase = final_discovered_count - initial_discovered_count

                        print("\n📈 Final counts:")
                        print(f"  repo table: {initial_repo_count} → {final_repo_count} (+{repo_increase})")
                        print(f"  discovered table: {initial_discovered_count} → {final_discovered_count} (+{discovered_increase})")

                        if repo_increase > 0:
                            print("✅ SUCCESS: Repositories were stored in main repo table!")
                        else:
                            print("❌ PROBLEM: No repositories were stored in main repo table")

                        if discovered_increase > 0:
                            print("✅ SUCCESS: Repositories were marked as discovered!")
                        else:
                            print("❌ PROBLEM: No repositories were marked as discovered")

                        # Check for any repos that were discovered but not stored
                        missing_repos = await conn.fetchval("""
                            SELECT COUNT(*)
                            FROM discovered_repositories dr
                            LEFT JOIN repo r ON dr.repo_id = r.id
                            WHERE r.id IS NULL
                            AND dr.matrix_index = $1;
                        """, matrix_index)

                        if missing_repos > 0:
                            print(f"⚠️  WARNING: {missing_repos} repos discovered but not stored (from this test)")
                        else:
                            print("✅ All discovered repos were properly stored")

                    finally:
                        await db_repo.release_connection(conn)

                else:
                    print("⚠️  No repositories found during crawl")

    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_storage_pipeline())
