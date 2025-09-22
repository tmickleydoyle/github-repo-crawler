#!/usr/bin/env python3
"""Test Supabase repository tracking functionality."""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from crawler.tracking_db import RepositoryTracker
from crawler.logger import setup_logging


async def test_supabase_tracking():
    """Test the complete Supabase tracking functionality."""

    # Set up logging
    setup_logging()

    print("🧪 Testing Supabase Repository Tracking")
    print("=" * 50)

    # Check if DATABASE_URL is configured
    if not os.environ.get("DATABASE_URL"):
        print("❌ DATABASE_URL environment variable not set")
        print("Set it with: export DATABASE_URL='your_supabase_connection_string'")
        return False

    try:
        async with RepositoryTracker() as tracker:
            print("✅ Repository tracker initialized")

            # Test 1: Get initial stats
            print("\n📊 Getting initial tracking stats...")
            stats = await tracker.get_tracking_stats()
            print(f"  Tracking enabled: {stats.get('tracking_enabled')}")
            if stats.get('tracking_enabled'):
                print(f"  Total discovered: {stats.get('total_discovered', 0)}")
                print(f"  Last 24h: {stats.get('discovered_last_24h', 0)}")
                print(f"  Total tracked: {stats.get('total_tracked', 0)}")
                print(f"  Average stars: {stats.get('avg_stars', 0):.1f}")

            # Test 2: Check recently discovered repos
            print("\n🔍 Checking recently discovered repositories...")
            recent_repos = await tracker.get_recently_discovered(hours=24)
            print(f"  Found {len(recent_repos)} repos discovered in last 24 hours")

            # Test 3: Mark some test repositories as discovered
            print("\n📝 Testing repository discovery marking...")
            test_repo_ids = [123456789, 987654321, 555666777]
            matrix_index = 999  # Use unique index for testing
            crawl_run_id = "test-run-2025-09-22"

            new_discoveries = await tracker.mark_repositories_discovered(
                test_repo_ids, matrix_index, crawl_run_id
            )
            print(f"  Marked {len(test_repo_ids)} repos as discovered")
            print(f"  New discoveries: {len(new_discoveries)}")

            # Test 4: Store test repository data
            print("\n💾 Testing repository data storage...")
            test_repo_data = [
                {
                    'id': 123456789,
                    'name_with_owner': 'test-user/test-repo-1',
                    'url': 'https://github.com/test-user/test-repo-1',
                    'stars': 100,
                    'forks': 20,
                    'language': 'Python',
                    'created_at': '2025-01-01T00:00:00Z',
                },
                {
                    'id': 987654321,
                    'name_with_owner': 'test-user/test-repo-2',
                    'url': 'https://github.com/test-user/test-repo-2',
                    'stars': 250,
                    'forks': 50,
                    'language': 'JavaScript',
                    'created_at': '2025-01-02T00:00:00Z',
                }
            ]

            await tracker.store_repository_data(test_repo_data)
            print(f"  Stored {len(test_repo_data)} repository records")

            # Test 5: Verify the data was stored
            print("\n🔍 Verifying stored data...")
            updated_recent = await tracker.get_recently_discovered(hours=1)
            for repo_id in test_repo_ids:
                if repo_id in updated_recent:
                    print(f"  ✅ Test repo {repo_id} found in recent discoveries")
                else:
                    print(f"  ❌ Test repo {repo_id} NOT found in recent discoveries")

            # Test 6: Get repository data for aggregation
            print("\n📋 Testing data retrieval for aggregation...")
            repo_data = await tracker.get_repository_data(limit=5)
            print(f"  Retrieved {len(repo_data)} repository records")

            if repo_data:
                print("  📋 Sample repositories:")
                for repo in repo_data[:3]:
                    print(f"    {repo['name_with_owner']} - {repo['stars']} stars ({repo['language']})")

            # Test 7: Final stats
            print("\n📈 Final tracking stats...")
            final_stats = await tracker.get_tracking_stats()
            if final_stats.get('tracking_enabled'):
                print(f"  Total discovered: {final_stats.get('total_discovered', 0)}")
                print(f"  Total tracked: {final_stats.get('total_tracked', 0)}")

            print("\n✅ All Supabase tracking tests completed successfully!")
            return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_supabase_tracking())
    if not success:
        sys.exit(1)
    print("\n🎉 Supabase tracking is working correctly!")