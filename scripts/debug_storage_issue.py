#!/usr/bin/env python3
"""Debug why repositories are being discovered but not stored."""

import asyncio
import os

if not os.environ.get("DATABASE_URL"):
    print("❌ DATABASE_URL environment variable not set")
    exit(1)

from crawler.db_repository import DatabaseRepository


async def debug_storage_issue():
    """Debug the storage issue."""
    print("🔍 Debugging Storage Issue")
    print("=" * 50)

    try:
        async with DatabaseRepository() as db_repo:
            conn = await db_repo.get_connection()

            try:
                print("1. 🔍 Checking discovered vs stored repositories...")

                # Get sample of discovered repos not in main table
                missing_repos = await conn.fetch("""
                    SELECT dr.repo_id, dr.first_discovered_at, dr.matrix_index, dr.crawl_run_id
                    FROM discovered_repositories dr
                    LEFT JOIN repo r ON dr.repo_id = r.id
                    WHERE r.id IS NULL
                    ORDER BY dr.first_discovered_at DESC
                    LIMIT 20;
                """)

                print(f"   📋 Sample of {len(missing_repos)} missing repositories:")
                for repo in missing_repos:
                    print(f"     ID: {repo['repo_id']}, Job: {repo['matrix_index']}, "
                          f"Run: {repo['crawl_run_id']}, Time: {repo['first_discovered_at']}")

                print("\n2. 🔍 Checking for storage errors in recent runs...")

                # Check if there are any patterns in the missing data
                run_analysis = await conn.fetch("""
                    SELECT
                        dr.crawl_run_id,
                        dr.matrix_index,
                        COUNT(*) as discovered_count,
                        COUNT(r.id) as stored_count,
                        COUNT(*) - COUNT(r.id) as missing_count
                    FROM discovered_repositories dr
                    LEFT JOIN repo r ON dr.repo_id = r.id
                    WHERE dr.first_discovered_at > NOW() - INTERVAL '48 hours'
                    GROUP BY dr.crawl_run_id, dr.matrix_index
                    ORDER BY dr.crawl_run_id DESC, dr.matrix_index;
                """)

                print("   📊 Storage success rate by run/job:")
                print("   Run ID     | Job | Discovered | Stored | Missing | Success Rate")
                print("   " + "-" * 65)
                for run in run_analysis:
                    success_rate = (run['stored_count'] / run['discovered_count'] * 100) if run['discovered_count'] > 0 else 0
                    print(f"   {run['crawl_run_id']:<10} | {run['matrix_index']:<3} | "
                          f"{run['discovered_count']:<10} | {run['stored_count']:<6} | "
                          f"{run['missing_count']:<7} | {success_rate:>6.1f}%")

                print("\n3. 🔍 Checking if this is a persistence vs storage issue...")

                # The issue might be in the order of operations:
                # 1. Repos are marked as discovered (persistence)
                # 2. But then storage fails silently

                print("   💡 Possible causes:")
                print("   • Storage method failing silently after persistence")
                print("   • Transaction rollback after persistence commit")
                print("   • Database connection issues during storage")
                print("   • Insufficient permissions for repo table")
                print("   • Storage timeout with large batches")

                print("\n4. 🧪 Testing storage functionality...")

                # Test if we can manually store a repository
                try:
                    test_repo_data = {
                        'id': 999999999,
                        'name': 'test-repo',
                        'name_with_owner': 'test-user/test-repo',
                        'url': 'https://github.com/test-user/test-repo',
                        'created_at': '2025-01-01T00:00:00Z',
                        'stars': 1,
                        'forks': 0,
                        'language': 'Python',
                        'owner': 'test-user',
                        'license': 'MIT',
                        'pushed_at': '2025-01-01T00:00:00Z',
                        'updated_at': '2025-01-01T00:00:00Z'
                    }

                    # Try to insert test repository
                    await conn.execute("""
                        INSERT INTO repo (
                            id, name, name_with_owner, url, created_at, stars, forks,
                            language, owner, license, pushed_at, updated_at, alphabet_partition
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
                        ) ON CONFLICT (id) DO NOTHING
                    """,
                    test_repo_data['id'], test_repo_data['name'], test_repo_data['name_with_owner'],
                    test_repo_data['url'], test_repo_data['created_at'], test_repo_data['stars'],
                    test_repo_data['forks'], test_repo_data['language'], test_repo_data['owner'],
                    test_repo_data['license'], test_repo_data['pushed_at'], test_repo_data['updated_at'],
                    test_repo_data['name'][0].lower()  # alphabet_partition
                    )

                    print("   ✅ Manual repository insertion: SUCCESS")

                    # Clean up test data
                    await conn.execute("DELETE FROM repo WHERE id = $1", test_repo_data['id'])

                except Exception as e:
                    print(f"   ❌ Manual repository insertion: FAILED - {e}")

            finally:
                await db_repo.release_connection(conn)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_storage_issue())