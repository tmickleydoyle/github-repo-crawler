"""Centralized database diagnostics and monitoring module.

Following CLAUDE.md principles: "Centralization, centralization, centralization"
This module provides all database diagnostic functionality in one place.
"""

import asyncio
from typing import Any

from .db_repository import DatabaseRepository


class DatabaseDiagnostics:
    """Centralized database diagnostics for maintenance and debugging.

    This class provides all database monitoring, debugging, and analysis
    functionality in a single, maintainable location.
    """

    def __init__(self, db_repository: DatabaseRepository):
        """Initialize diagnostics with database repository."""
        self.db_repo = db_repository

    async def get_storage_analysis(self) -> dict[str, Any]:
        """Comprehensive storage analysis and health check."""
        conn = await self.db_repo.get_connection()
        try:
            # Get table row counts
            repo_count = await conn.fetchval("SELECT COUNT(*) FROM repo")
            repo_stats_count = await conn.fetchval("SELECT COUNT(*) FROM repo_stats")
            discovered_count = await conn.fetchval(
                "SELECT COUNT(*) FROM discovered_repositories"
            )

            # Get database size information
            db_size = await conn.fetchval(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            )

            # Get table sizes
            table_sizes = await conn.fetch("""
                SELECT
                    tablename,
                    pg_size_pretty(
                        pg_total_relation_size('public.'||tablename)
                    ) as size,
                    pg_total_relation_size('public.'||tablename) as size_bytes
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size('public.'||tablename) DESC;
            """)

            # Check for data inconsistencies
            missing_repos = await conn.fetchval("""
                SELECT COUNT(*)
                FROM discovered_repositories dr
                LEFT JOIN repo r ON dr.repo_id = r.id
                WHERE r.id IS NULL;
            """)

            # Get matrix job breakdown
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

            # Calculate storage efficiency
            total_size_bytes = sum(table["size_bytes"] for table in table_sizes)
            size_mb = total_size_bytes / (1024 * 1024)
            free_limit_mb = 500  # Supabase free tier

            return {
                "table_counts": {
                    "repo": repo_count,
                    "repo_stats": repo_stats_count,
                    "discovered_repositories": discovered_count,
                },
                "storage": {
                    "total_size": db_size,
                    "size_mb": round(size_mb, 2),
                    "usage_percent": round(size_mb / free_limit_mb * 100, 1),
                    "table_sizes": [dict(row) for row in table_sizes],
                },
                "data_integrity": {
                    "missing_repos": missing_repos,
                    "consistency_rate": round(
                        (discovered_count - missing_repos) / discovered_count * 100, 1
                    )
                    if discovered_count > 0
                    else 100,
                },
                "matrix_jobs": [dict(row) for row in matrix_stats],
            }

        finally:
            await self.db_repo.release_connection(conn)

    async def get_crawl_performance_analysis(self) -> dict[str, Any]:
        """Analyze crawl performance and identify issues."""
        conn = await self.db_repo.get_connection()
        try:
            # Recent crawl runs analysis
            recent_runs = await conn.fetch("""
                SELECT
                    crawl_run_id,
                    COUNT(*) as repos_discovered,
                    MIN(first_discovered_at) as run_start,
                    MAX(last_seen_at) as run_end,
                    COUNT(DISTINCT matrix_index) as jobs_used
                FROM discovered_repositories
                WHERE first_discovered_at > NOW() - INTERVAL '48 hours'
                GROUP BY crawl_run_id
                ORDER BY run_start DESC;
            """)

            # Storage success rate by run/job
            storage_analysis = await conn.fetch("""
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

            # Overall statistics
            total_stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_discovered,
                    COUNT(DISTINCT matrix_index) as matrix_jobs_used,
                    MIN(first_discovered_at) as first_discovery,
                    MAX(last_seen_at) as last_discovery,
                    COUNT(*) FILTER (
                        WHERE last_seen_at > NOW() - INTERVAL '24 hours'
                    ) as discovered_last_24h,
                    COUNT(*) FILTER (WHERE discovery_count > 1) as rediscovered_repos
                FROM discovered_repositories
            """)

            return {
                "recent_runs": [dict(row) for row in recent_runs],
                "storage_efficiency": [dict(row) for row in storage_analysis],
                "overall_stats": dict(total_stats) if total_stats else {},
            }

        finally:
            await self.db_repo.release_connection(conn)

    async def check_schema_health(self) -> dict[str, Any]:
        """Check database schema health and structure."""
        conn = await self.db_repo.get_connection()
        try:
            # Get all table schemas
            tables_info = {}

            for table in ["repo", "repo_stats", "discovered_repositories"]:
                columns = await conn.fetch(
                    """
                    SELECT
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_name = $1 AND table_schema = 'public'
                    ORDER BY ordinal_position;
                """,
                    table,
                )

                tables_info[table] = [dict(col) for col in columns]

            # Check for required indexes
            indexes = await conn.fetch("""
                SELECT
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                ORDER BY tablename, indexname;
            """)

            return {"tables": tables_info, "indexes": [dict(idx) for idx in indexes]}

        finally:
            await self.db_repo.release_connection(conn)

    async def test_storage_functionality(self) -> dict[str, Any]:
        """Test database storage functionality."""
        conn = await self.db_repo.get_connection()
        try:
            # Test repository insertion
            test_repo_id = 999999999
            test_results: dict[str, Any] = {
                "repo_insert": False,
                "repo_stats_insert": False,
                "discovered_insert": False,
                "cleanup": False,
            }

            try:
                # Test repo table insert
                await conn.execute(
                    """
                    INSERT INTO repo (
                        id, name, owner, url, name_with_owner, alphabet_partition
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (id) DO NOTHING
                """,
                    test_repo_id,
                    "test-repo",
                    "test-user",
                    "https://github.com/test-user/test-repo",
                    "test-user/test-repo",
                    "t",
                )
                test_results["repo_insert"] = True

                # Test repo_stats insert
                await conn.execute(
                    """
                    INSERT INTO repo_stats (repo_id, fetched_date, stars)
                    VALUES ($1, CURRENT_DATE, $2)
                    ON CONFLICT (repo_id, fetched_date) DO NOTHING
                """,
                    test_repo_id,
                    1,
                )
                test_results["repo_stats_insert"] = True

                # Test discovered_repositories insert
                await conn.execute(
                    """
                    INSERT INTO discovered_repositories (
                        repo_id, matrix_index, crawl_run_id
                    )
                    VALUES ($1, $2, $3)
                    ON CONFLICT (repo_id) DO NOTHING
                """,
                    test_repo_id,
                    99,
                    "test-run",
                )
                test_results["discovered_insert"] = True

                # Cleanup test data
                await conn.execute(
                    "DELETE FROM repo_stats WHERE repo_id = $1", test_repo_id
                )
                await conn.execute(
                    "DELETE FROM discovered_repositories WHERE repo_id = $1",
                    test_repo_id,
                )
                await conn.execute("DELETE FROM repo WHERE id = $1", test_repo_id)
                test_results["cleanup"] = True

            except Exception as e:
                test_results["error"] = str(e)

            return test_results

        finally:
            await self.db_repo.release_connection(conn)

    async def generate_comprehensive_report(self) -> str:
        """Generate a comprehensive database health report."""
        storage = await self.get_storage_analysis()
        performance = await self.get_crawl_performance_analysis()
        await self.check_schema_health()
        functionality = await self.test_storage_functionality()

        report = []
        report.append("=" * 80)
        report.append("DATABASE HEALTH REPORT")
        report.append("=" * 80)

        # Storage Analysis
        report.append("\n📊 STORAGE ANALYSIS")
        report.append("-" * 40)
        report.append(f"Total Database Size: {storage['storage']['total_size']}")
        report.append(
            f"Usage: {storage['storage']['size_mb']} MB "
            f"({storage['storage']['usage_percent']}% of free tier)"
        )

        report.append("\nTable Counts:")
        for table, count in storage["table_counts"].items():
            report.append(f"  • {table}: {count:,} rows")

        # Data Integrity
        report.append("\n🔍 DATA INTEGRITY")
        report.append("-" * 40)
        report.append(
            f"Consistency Rate: {storage['data_integrity']['consistency_rate']}%"
        )
        if storage["data_integrity"]["missing_repos"] > 0:
            report.append(
                f"⚠️  Missing repos in main table: "
                f"{storage['data_integrity']['missing_repos']:,}"
            )
        else:
            report.append("✅ All discovered repos are properly stored")

        # Performance Analysis
        report.append("\n📈 CRAWL PERFORMANCE")
        report.append("-" * 40)
        overall = performance["overall_stats"]
        if overall:
            report.append(f"Total Discovered: {overall['total_discovered']:,}")
            report.append(f"Last 24h: {overall['discovered_last_24h']:,}")
            report.append(f"Matrix Jobs Used: {overall['matrix_jobs_used']}")

        if performance["recent_runs"]:
            report.append("\nRecent Crawl Runs:")
            for run in performance["recent_runs"][:5]:
                report.append(
                    f"  • {run['crawl_run_id']}: {run['repos_discovered']:,} repos, "
                    f"{run['jobs_used']} jobs"
                )

        # Functionality Test
        report.append("\n🧪 FUNCTIONALITY TEST")
        report.append("-" * 40)
        if functionality.get("error"):
            report.append(f"❌ Storage test failed: {functionality['error']}")
        else:
            all_passed = all(
                functionality[key]
                for key in [
                    "repo_insert",
                    "repo_stats_insert",
                    "discovered_insert",
                    "cleanup",
                ]
            )
            report.append(
                "✅ All storage operations working correctly"
                if all_passed
                else "⚠️  Some storage issues detected"
            )

        report.append("\n" + "=" * 80)
        return "\n".join(report)


async def run_diagnostics_cli() -> None:
    """CLI entry point for database diagnostics."""
    import os

    if not os.environ.get("DATABASE_URL"):
        print("❌ DATABASE_URL environment variable not set")
        print("Set it with: export DATABASE_URL='your_connection_string'")
        return

    async with DatabaseRepository() as db_repo:
        diagnostics = DatabaseDiagnostics(db_repo)
        report = await diagnostics.generate_comprehensive_report()
        print(report)


if __name__ == "__main__":
    asyncio.run(run_diagnostics_cli())
