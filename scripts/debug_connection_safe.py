#!/usr/bin/env python3
"""Debug script to test Supabase connection and identify issues."""

import asyncio
import os

# Use environment variable - DO NOT hardcode credentials!
if not os.environ.get("DATABASE_URL"):
    print("❌ DATABASE_URL environment variable not set")
    print("Set it with: export DATABASE_URL='your_connection_string'")
    exit(1)

from crawler.db_repository import DatabaseRepository


async def debug_connection():
    """Test connection and debug issues."""
    print("🔍 Debugging Supabase Connection")
    print("=" * 50)

    try:
        print("1. Testing database connection...")
        async with DatabaseRepository() as db_repo:
            print("   ✅ Connection established")

            print("2. Initializing schema...")
            await db_repo.initialize_schema()
            print("   ✅ Schema initialized")

            print("3. Checking existing data...")
            stats = await db_repo.get_discovery_stats()
            print(f"   📊 Total repositories: {stats['total_discovered']}")
            print(f"   📊 Last 24h: {stats['discovered_last_24h']}")

            print("4. Testing data insertion...")
            # Test marking some fake repositories as discovered
            test_repo_ids = [12345, 67890, 11111]
            new_ids = await db_repo.mark_repositories_discovered(
                test_repo_ids, matrix_index=99, crawl_run_id="debug-test"
            )
            print(f"   ✅ Inserted {len(new_ids)} test repositories")

            print("5. Verifying insertion...")
            updated_stats = await db_repo.get_discovery_stats()
            print(f"   📊 Total repositories now: {updated_stats['total_discovered']}")

            if updated_stats['total_discovered'] > stats['total_discovered']:
                print("   ✅ Data insertion working correctly")
            else:
                print("   ❌ Data insertion failed")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nPossible issues:")
        print("• Connection string format incorrect")
        print("• Password has special characters that need escaping")
        print("• Supabase project not accessible")
        print("• IP not allowlisted in Supabase")
        print("• Database permissions insufficient")


if __name__ == "__main__":
    asyncio.run(debug_connection())