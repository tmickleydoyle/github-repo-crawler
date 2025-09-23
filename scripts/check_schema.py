#!/usr/bin/env python3
"""Check the actual database schema vs expected schema."""

import asyncio
import os

if not os.environ.get("DATABASE_URL"):
    print("❌ DATABASE_URL environment variable not set")
    exit(1)

from crawler.db_repository import DatabaseRepository


async def check_schema():
    """Check actual vs expected database schema."""
    print("🔍 Checking Database Schema")
    print("=" * 50)

    try:
        async with DatabaseRepository() as db_repo:
            conn = await db_repo.get_connection()

            try:
                print("1. 📋 Checking 'repo' table schema...")

                # Get actual columns in repo table
                repo_columns = await conn.fetch("""
                    SELECT
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_name = 'repo'
                    AND table_schema = 'public'
                    ORDER BY ordinal_position;
                """)

                print("   Current 'repo' table columns:")
                for col in repo_columns:
                    nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                    default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                    print(f"     {col['column_name']:<20} {col['data_type']:<15} {nullable}{default}")

                print("\n2. 📋 Checking 'repo_stats' table schema...")

                # Get repo_stats columns
                stats_columns = await conn.fetch("""
                    SELECT
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_name = 'repo_stats'
                    AND table_schema = 'public'
                    ORDER BY ordinal_position;
                """)

                print("   Current 'repo_stats' table columns:")
                for col in stats_columns:
                    nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                    default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                    print(f"     {col['column_name']:<20} {col['data_type']:<15} {nullable}{default}")

                print("\n3. 🔍 Checking 'discovered_repositories' table schema...")

                # Get discovered_repositories columns
                discovered_columns = await conn.fetch("""
                    SELECT
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_name = 'discovered_repositories'
                    AND table_schema = 'public'
                    ORDER BY ordinal_position;
                """)

                print("   Current 'discovered_repositories' table columns:")
                for col in discovered_columns:
                    nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                    default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                    print(f"     {col['column_name']:<20} {col['data_type']:<15} {nullable}{default}")

                print("\n4. ❌ Schema Issues Found:")

                # Expected columns that might be missing
                expected_repo_columns = [
                    'id', 'name', 'name_with_owner', 'url', 'created_at',
                    'stars', 'forks', 'language', 'owner', 'license',
                    'pushed_at', 'updated_at', 'alphabet_partition'
                ]

                actual_repo_columns = [col['column_name'] for col in repo_columns]

                missing_columns = set(expected_repo_columns) - set(actual_repo_columns)
                extra_columns = set(actual_repo_columns) - set(expected_repo_columns)

                if missing_columns:
                    print(f"   🚨 Missing columns in 'repo' table: {', '.join(missing_columns)}")

                if extra_columns:
                    print(f"   ℹ️  Extra columns in 'repo' table: {', '.join(extra_columns)}")

                if not missing_columns and not extra_columns:
                    print("   ✅ repo table schema matches expectations")

                print("\n5. 💡 Expected vs Actual Schema:")
                print("   The code expects 'stars' to be in the 'repo' table")
                print("   But it might be in 'repo_stats' table for historical tracking")
                print("   This is likely a design where:")
                print("   • 'repo' = static repository info")
                print("   • 'repo_stats' = time-series data (stars over time)")

            finally:
                await db_repo.release_connection(conn)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_schema())
