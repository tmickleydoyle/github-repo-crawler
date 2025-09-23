#!/usr/bin/env python3
"""Check Supabase storage usage and investigate storage issues."""

import asyncio
import os

# Use environment variable
if not os.environ.get("DATABASE_URL"):
    print("❌ DATABASE_URL environment variable not set")
    print("Set it with: export DATABASE_URL='your_connection_string'")
    exit(1)

from crawler.db_repository import DatabaseRepository


async def check_storage_and_data():
    """Check storage usage and data consistency."""
    print("🔍 Checking Supabase Storage and Data")
    print("=" * 60)

    try:
        async with DatabaseRepository() as db_repo:
            # Get connection for direct SQL queries
            conn = await db_repo.get_connection()

            try:
                print("1. 📊 Checking table sizes and row counts...")

                # Check all tables and their sizes
                tables_info = await conn.fetch("""
                    SELECT
                        schemaname,
                        tablename,
                        attname,
                        n_distinct,
                        correlation
                    FROM pg_stats
                    WHERE schemaname = 'public'
                    ORDER BY tablename, attname;
                """)

                # Get row counts for each table
                repo_count = await conn.fetchval("SELECT COUNT(*) FROM repo")
                repo_stats_count = await conn.fetchval("SELECT COUNT(*) FROM repo_stats")
                discovered_count = await conn.fetchval("SELECT COUNT(*) FROM discovered_repositories")

                print(f"   📦 repo table: {repo_count:,} rows")
                print(f"   📈 repo_stats table: {repo_stats_count:,} rows")
                print(f"   🔍 discovered_repositories table: {discovered_count:,} rows")

                print("\n2. 🗄️ Checking database size...")

                # Check database size
                db_size = await conn.fetchval("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """)
                print(f"   💾 Total database size: {db_size}")

                # Check table sizes
                table_sizes = await conn.fetch("""
                    SELECT
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                        pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
                """)

                for table in table_sizes:
                    print(f"   📋 {table['tablename']}: {table['size']}")

                print("\n3. 🔍 Checking discovered_repositories details...")

                # Check discovered repositories by matrix job
                matrix_stats = await conn.fetch("""
                    SELECT
                        matrix_index,
                        COUNT(*) as repo_count,
                        MIN(first_discovered_at) as first_discovery,
                        MAX(last_seen_at) as last_discovery
                    FROM discovered_repositories
                    GROUP BY matrix_index
                    ORDER BY matrix_index;
                """)

                print("   Matrix job breakdown:")
                total_discovered = 0
                for stat in matrix_stats:
                    total_discovered += stat['repo_count']
                    print(f"     Job {stat['matrix_index']}: {stat['repo_count']:,} repos")

                print(f"   📊 Total in discovered_repositories: {total_discovered:,}")

                print("\n4. 🔍 Checking for data inconsistencies...")

                # Check if repos in discovered_repositories are also in repo table
                missing_repos = await conn.fetchval("""
                    SELECT COUNT(*)
                    FROM discovered_repositories dr
                    LEFT JOIN repo r ON dr.repo_id = r.id
                    WHERE r.id IS NULL;
                """)

                print(f"   ⚠️  Discovered repos NOT in main repo table: {missing_repos:,}")

                if missing_repos > 0:
                    print("   💡 This suggests repos were discovered but not stored in main table")

                    # Check if there were any storage errors
                    recent_discoveries = await conn.fetch("""
                        SELECT repo_id, first_discovered_at, matrix_index
                        FROM discovered_repositories dr
                        LEFT JOIN repo r ON dr.repo_id = r.id
                        WHERE r.id IS NULL
                        ORDER BY first_discovered_at DESC
                        LIMIT 10;
                    """)

                    print("   📋 Recent missing repos (sample):")
                    for repo in recent_discoveries:
                        print(f"     Repo ID {repo['repo_id']}: discovered at {repo['first_discovered_at']} (job {repo['matrix_index']})")

                print("\n5. 📈 Checking recent crawl activity...")

                # Check recent crawl runs
                recent_runs = await conn.fetch("""
                    SELECT
                        crawl_run_id,
                        COUNT(*) as repos_discovered,
                        MIN(first_discovered_at) as run_start,
                        MAX(last_seen_at) as run_end,
                        COUNT(DISTINCT matrix_index) as jobs_used
                    FROM discovered_repositories
                    WHERE first_discovered_at > NOW() - INTERVAL '24 hours'
                    GROUP BY crawl_run_id
                    ORDER BY run_start DESC;
                """)

                print("   Recent crawl runs:")
                for run in recent_runs:
                    duration = run['run_end'] - run['run_start'] if run['run_end'] and run['run_start'] else 'Unknown'
                    print(f"     Run {run['crawl_run_id']}: {run['repos_discovered']:,} repos, {run['jobs_used']} jobs, duration: {duration}")

                print("\n6. 🚨 Storage Limit Analysis...")

                # Calculate if we're near storage limits
                total_size_bytes = sum(table['size_bytes'] for table in table_sizes)
                size_mb = total_size_bytes / (1024 * 1024)

                print(f"   💾 Current usage: {size_mb:.1f} MB")

                # Supabase free tier limits
                free_limit_mb = 500  # 500MB free tier
                if size_mb > free_limit_mb * 0.8:  # 80% of limit
                    print(f"   🚨 WARNING: Using {size_mb/free_limit_mb*100:.1f}% of free tier limit ({free_limit_mb}MB)")
                    print("   💡 Consider upgrading Supabase plan or cleaning old data")
                else:
                    print(f"   ✅ Storage usage OK: {size_mb/free_limit_mb*100:.1f}% of free tier limit")

            finally:
                await db_repo.release_connection(conn)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_storage_and_data())
