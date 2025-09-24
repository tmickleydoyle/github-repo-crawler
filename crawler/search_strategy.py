"""
Optimized search strategy for GitHub repository discovery.

This module exposes a single, robust strategy implementation focused on
deterministic, high-coverage query generation while respecting API limits.
Dead/duplicate approaches have been removed to keep maintenance simple.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from .domain import SearchQuery


class SimpleSearchStrategy:
    """Deterministic hour-based search strategy for maximum repository coverage.

    Each hour gets unique, non-overlapping queries using:
    - Hash-based distribution for topics
    - Round-robin for languages
    - Logarithmic star range partitioning
    - Date sampling across multiple time periods
    """

    @staticmethod
    def calculate_search_space() -> dict[str, Any]:
        """Estimate total search space coverage for planning/scaling.

        Returns a coarse breakdown useful for capacity planning. This mirrors
        the previous calculator but keeps it centralized in the single strategy.
        """
        # Keep estimates simple and transparent
        languages = 60
        star_buckets = 7
        pushed_days_sample = 720  # rolling 2 years of per-day sampling windows
        name_keywords = 96
        size_buckets = 6

        combinations = {
            "name_stars": name_keywords * star_buckets,
            "pushed_stars": pushed_days_sample * star_buckets,
            "language_stars": languages * 5,  # 5 broad star ranges per lang
            "size_stars": size_buckets * 3,
        }

        total = sum(combinations.values())
        max_repos = total * 1000  # theoretical max per GitHub Search API

        return {
            "total_combinations": total,
            "max_repos_theoretical": max_repos,
            "breakdown": combinations,
            "recommended_matrix_jobs": min(200, max(10, total // 50)),
        }

    def generate_queries(
        self, matrix_index: int = 0, matrix_total: int = 1
    ) -> list[SearchQuery]:
        """Generate high-volume search queries for 10M repos/day target.

        Strategy for maximum coverage:
        - Use 'pushed' date ranges to get recently active repos
        - Each hour gets different date offset to ensure uniqueness
        - Broad star ranges that return 1000 results each
        - Minimize restrictive filters
        """
        if matrix_total == 1:
            # Single job: use created dates starting from 2025-01-01
            start_date = datetime(2025, 1, 1, tzinfo=UTC)
            queries: list[SearchQuery] = []

            # Query 50 different days with various star ranges
            for day_offset in range(50):
                target_date = start_date - timedelta(days=day_offset)
                date_str = target_date.strftime("%Y-%m-%d")
                star_buckets = [
                    "0..10",
                    "11..50",
                    "51..100",
                    "101..500",
                    "501..1000",
                    "1001..5000",
                    ">5000",
                ]
                for stars in star_buckets:
                    if len(queries) >= 1000:  # Limit to 1000 queries for max coverage
                        break
                    queries.append(
                        SearchQuery(
                            f"is:public created:{date_str} stars:{stars} sort:updated",
                            f"Created {date_str}, stars:{stars}",
                            1000,
                        )
                    )
                if len(queries) >= 1000:
                    break
            return queries

        # Get current hour and day for deterministic partitioning
        current_hour = datetime.now(UTC).hour
        current_day_of_year = datetime.now(UTC).timetuple().tm_yday

        all_combos = []

        # Common repository name keywords distributed across hours for massive coverage
        # Each hour gets different keywords to ensure uniqueness
        repo_name_keywords = [
            "app",
            "api",
            "web",
            "bot",
            "lib",
            "test",
            "demo",
            "cli",
            "sdk",
            "ui",
            "server",
            "client",
            "admin",
            "mobile",
            "react",
            "vue",
            "angular",
            "node",
            "python",
            "java",
            "go",
            "rust",
            "docker",
            "kubernetes",
            "auth",
            "data",
            "ml",
            "ai",
            "game",
            "tool",
            "util",
            "service",
            "micro",
            "backend",
            "frontend",
            "fullstack",
            "cms",
            "blog",
            "shop",
            "store",
            "chat",
            "social",
            "dashboard",
            "monitor",
            "logger",
            "parser",
            "generator",
            "framework",
            "plugin",
            "extension",
            "starter",
            "template",
            "boilerplate",
            "example",
            "tutorial",
            "learning",
            "project",
            "homework",
            "practice",
            "exercise",
            "challenge",
            "clone",
            "mock",
            "sample",
            "prototype",
            "poc",
            "mvp",
            "portfolio",
            "personal",
            "website",
            "page",
            "landing",
            "portfolio",
            "resume",
            "cv",
            "scraper",
            "crawler",
            "spider",
            "fetch",
            "download",
            "upload",
            "sync",
            "converter",
            "transformer",
            "processor",
            "analyzer",
            "validator",
            "checker",
            "manager",
            "handler",
            "controller",
            "worker",
            "queue",
            "task",
            "job",
            "scheduler",
            "cron",
            "automation",
            "deploy",
            "ci",
            "cd",
            "devops",
            "infra",
            "terraform",
            "ansible",
            "jenkins",
            "github",
            "gitlab",
            "action",
            "script",
            "code",
            "dev",
            "prod",
            "staging",
            "local",
            "config",
            "env",
        ]

        # Distribute keywords across hours with day-of-year rotation
        # Ensure Hour 0 today differs from Hour 0 tomorrow (uniqueness)
        keywords_per_hour = max(1, len(repo_name_keywords) // 24)

        # Rotate keywords based on day AND hour to ensure uniqueness across days
        day_rotation_offset = (current_day_of_year * keywords_per_hour) % len(
            repo_name_keywords
        )
        hour_start_index = (
            current_hour * keywords_per_hour + day_rotation_offset
        ) % len(repo_name_keywords)

        # Get keywords for this hour (wrapping around if necessary)
        hour_keywords = []
        for i in range(keywords_per_hour):
            idx = (hour_start_index + i) % len(repo_name_keywords)
            hour_keywords.append(repo_name_keywords[idx])

        # Strategy 1: Name-based queries with star ranges
        # Each matrix job gets different keywords + star combinations
        keywords_per_job = (
            max(1, len(hour_keywords) // matrix_total)
            if matrix_total > 1
            else len(hour_keywords)
        )
        job_keywords = (
            hour_keywords[
                matrix_index * keywords_per_job : (matrix_index + 1) * keywords_per_job
            ]
            if keywords_per_job < len(hour_keywords)
            else hour_keywords
        )

        star_buckets = [
            "0..10",
            "11..50",
            "51..100",
            "101..500",
            "501..1000",
            "1001..5000",
            ">5000",
        ]

        # Generate name + stars queries (use more keywords per worker)
        for keyword in job_keywords[:15]:  # Increase keywords for more queries
            for stars in star_buckets:
                all_combos.append(
                    {
                        "query": (
                            f"is:public {keyword} in:name stars:{stars} sort:updated"
                        ),
                        "desc": (f"Name contains '{keyword}', stars:{stars}"),
                    }
                )

        # Strategy 2: Single-day created dates for maximum uniqueness (PRIMARY STRATEGY)
        # Start from 2025-01-01 and work backwards, each job gets unique days
        start_date = datetime(2025, 1, 1, tzinfo=UTC)

        # Each matrix job gets a unique set of days to query
        # With 40 workers, each gets 100 unique days = 4000 total days covered
        days_per_job = 100  # Each job queries 100 different days with 6 star ranges each = 600 queries
        job_start_day = matrix_index * days_per_job

        for day_offset in range(job_start_day, job_start_day + days_per_job):
            target_date = start_date - timedelta(days=day_offset)
            date_str = target_date.strftime("%Y-%m-%d")

            # Multiple star ranges per day for better coverage
            # Also add fork variants to capture even more repos
            star_ranges = [
                "0..10",
                "11..50",
                "51..100",
                "101..500",
                "501..1000",
                ">1000",
            ]
            for stars in star_ranges:
                # Regular query
                all_combos.append(
                    {
                        "query": (
                            f"is:public created:{date_str} stars:{stars} sort:updated"
                        ),
                        "desc": f"Created {date_str}, stars:{stars}",
                    }
                )
                # Add fork variant for additional coverage
                if stars in ["0..10", "11..50"]:  # Only for low star ranges
                    all_combos.append(
                        {
                            "query": (
                                f"is:public fork:true created:{date_str} stars:{stars} sort:updated"
                            ),
                            "desc": f"Fork created {date_str}, stars:{stars}",
                        }
                    )

        # Strategy 3: Language-based queries without date filters
        # Top languages that have millions of repos
        top_languages = [
            "javascript",
            "python",
            "java",
            "html",
            "typescript",
            "css",
            "c++",
            "php",
            "c#",
            "ruby",
            "go",
            "c",
            "shell",
            "jupyter notebook",
            "swift",
            "kotlin",
        ]

        # Each job gets different languages
        langs_per_job = max(1, len(top_languages) // min(matrix_total, 20))
        job_langs = top_languages[
            (matrix_index * langs_per_job) % len(top_languages) : (
                (matrix_index + 1) * langs_per_job
            )
            % len(top_languages)
        ]

        for lang in job_langs:
            # Broad star ranges for maximum results
            for stars in ["0..5", "6..20", "21..100", "101..1000", ">1000"]:
                all_combos.append(
                    {
                        "query": (
                            f'is:public language:"{lang}" stars:{stars} sort:updated'
                        ),
                        "desc": f"Lang:{lang}, stars:{stars}",
                    }
                )

        # Strategy 3: Size-based queries for repos without language detection
        size_buckets = [
            "0..100",  # Very small repos
            "100..500",  # Small
            "500..1000",  # Medium
            "1000..5000",  # Large
            "5000..50000",  # Very large
            ">50000",  # Huge
        ]

        # Distribute size ranges across jobs
        size_idx = matrix_index % len(size_buckets)
        job_sizes = (
            size_buckets[size_idx : size_idx + 2]
            if size_idx < len(size_buckets) - 1
            else [size_buckets[size_idx]]
        )

        for size in job_sizes:
            for stars in ["0..10", "11..100", ">100"]:
                all_combos.append(
                    {
                        "query": f"is:public size:{size} stars:{stars} sort:updated",
                        "desc": f"Size:{size}KB, stars:{stars}",
                    }
                )

        # Convert to SearchQuery objects - maximize queries per worker
        # Each worker can handle many queries to maximize repo discovery
        queries = []
        for combo in all_combos[
            :1000
        ]:  # Increase to 1000 queries per job for maximum coverage
            queries.append(
                SearchQuery(
                    query_string=combo["query"],
                    description=f"Job {matrix_index}/{matrix_total}: {combo['desc']}",
                    expected_results=1000,
                )
            )

        # Always add diverse broad queries for better coverage
        if len(queries) < 1000:
            # Add diverse queries using different filters
            broad_queries = [
                "is:public stars:0..5",
                "is:public stars:6..10",
                "is:public stars:11..20",
                "is:public stars:21..50",
                "is:public stars:51..100",
                "is:public stars:101..500",
                "is:public stars:501..1000",
                "is:public stars:>1000",
                "is:public fork:false stars:0..10",
                "is:public fork:true stars:0..10",
                "is:public archived:false stars:0..50",
                "is:public forks:0 stars:0..20",
                "is:public forks:1..5 stars:0..20",
                "is:public forks:>5 stars:0..20",
                f"is:public created:>{datetime.now(UTC).year - 1}-01-01 stars:0..10",
                f"is:public created:{datetime.now(UTC).year - 2}-01-01..{datetime.now(UTC).year - 2}-12-31",
                f"is:public updated:>{datetime.now(UTC).year}-01-01 stars:0..5",
            ]

            for q in broad_queries:
                if len(queries) >= 1000:
                    break
                queries.append(
                    SearchQuery(
                        query_string=f"{q} sort:updated",
                        description=f"Job {matrix_index}: Broad - {q}",
                        expected_results=1000,
                    )
                )

        return queries


# Backwards compatibility: keep the old name pointing to the single strategy
# This preserves external imports like `from crawler.search_strategy import SearchStrategy`
SearchStrategy = SimpleSearchStrategy
