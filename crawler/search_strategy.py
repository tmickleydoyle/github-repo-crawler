"""
Optimized search strategy for GitHub repository discovery.

This module provides a simplified, more effective approach to discovering
diverse GitHub repositories while respecting API limits.
"""

from dataclasses import dataclass

from .domain import SearchQuery


@dataclass
class SearchStrategy:
    """Strategy for generating GitHub search queries."""

    def generate_queries(
        self, matrix_index: int = 0, matrix_total: int = 1
    ) -> list[SearchQuery]:
        """
        Generate optimized search queries for discovering diverse repositories.

        This simplified strategy focuses on:
        1. Language diversity
        2. Star count ranges that have good coverage
        3. Temporal distribution
        4. Simple, reliable queries
        """
        if matrix_total == 1:
            return self._get_basic_queries()

        return self._get_partitioned_queries(matrix_index, matrix_total)

    def _get_basic_queries(self) -> list[SearchQuery]:
        """Generate basic queries for single-job execution."""
        return [
            SearchQuery(
                query_string="is:public stars:1..10 sort:updated",
                description="Low star count repositories, recently updated",
                expected_results=1000,
            ),
            SearchQuery(
                query_string="is:public stars:11..50 sort:stars",
                description="Medium star count repositories",
                expected_results=1000,
            ),
            SearchQuery(
                query_string="is:public stars:51..200 sort:updated",
                description="Higher star count repositories",
                expected_results=1000,
            ),
            SearchQuery(
                query_string="is:public stars:>200 sort:stars",
                description="Popular repositories",
                expected_results=1000,
            ),
        ]

    def _get_partitioned_queries(
        self, matrix_index: int, matrix_total: int
    ) -> list[SearchQuery]:
        """Generate queries partitioned across matrix jobs with NO OVERLAPS.

        Key improvements:
        - Deterministic assignment prevents any duplicate queries between jobs
        - Each job gets unique, non-overlapping search spaces
        - Maximizes coverage while eliminating redundancy
        """

        languages = [
            "javascript",
            "python",
            "java",
            "typescript",
            "go",
            "rust",
            "php",
            "c++",
            "c#",
            "ruby",
            "swift",
            "kotlin",
            "scala",
            "dart",
            "r",
            "objective-c",
            "perl",
            "haskell",
            "lua",
            "clojure",
            "f#",
            "erlang",
            "elixir",
            "crystal",
            "nim",
            "julia",
            "zig",
            "v",
            "assembly",
            "shell",
            "powershell",
            "makefile",
            "dockerfile",
            "html",
            "css",
            "scss",
            "less",
            "vue",
            "svelte",
            "coffeescript",
            "livescript",
        ]

        star_ranges = [
            "0..2",
            "3..5",
            "6..10",
            "11..15",
            "16..25",
            "26..40",
            "41..60",
            "61..90",
            "91..130",
            "131..180",
            "181..250",
            "251..350",
            "351..500",
            "501..700",
            "701..1000",
            "1001..1400",
            "1401..2000",
            "2001..3000",
            "3001..4500",
            "4501..7000",
            "7001..10000",
            "10001..15000",
            "15001..25000",
            "25001..50000",
            ">50000",
        ]

        time_ranges = [
            "2024-06-01..2025-12-31",
            "2024-01-01..2024-05-31",
            "2023-07-01..2023-12-31",
            "2023-01-01..2023-06-30",
            "2022-06-01..2022-12-31",
            "2022-01-01..2022-05-31",
            "2021-06-01..2021-12-31",
            "2021-01-01..2021-05-31",
            "2020-01-01..2020-12-31",
            "..2019-12-31",
        ]

        topics = [
            "api",
            "cli",
            "framework",
            "library",
            "tool",
            "web",
            "mobile",
            "game",
            "machine-learning",
            "data",
            "security",
            "blockchain",
            "iot",
            "ai",
            "database",
            "monitoring",
            "testing",
            "automation",
            "devops",
            "cloud",
        ]

        # CRITICAL FIX: Deterministic, non-overlapping query generation
        # Each matrix job gets a unique slice of the total search space
        all_combos = []

        # Build all possible combinations in a deterministic order
        # Priority 1: Language + Stars (most granular)
        for lang in languages:
            for stars in star_ranges:
                all_combos.append({
                    "type": "lang_stars",
                    "query": f"is:public language:{lang} stars:{stars} fork:false archived:false sort:updated",
                    "desc": f"Lang+Stars: {lang}, {stars} stars"
                })

        # Priority 2: Time + Stars
        for time in time_ranges:
            for stars in star_ranges:
                all_combos.append({
                    "type": "time_stars",
                    "query": f"is:public created:{time} stars:{stars} fork:false sort:updated",
                    "desc": f"Time+Stars: {time}, {stars} stars"
                })

        # Priority 3: Topic + Stars
        for topic in topics:
            for stars in star_ranges:
                all_combos.append({
                    "type": "topic_stars",
                    "query": f"is:public topic:{topic} stars:{stars} fork:false sort:updated",
                    "desc": f"Topic+Stars: {topic}, {stars} stars"
                })

        # Priority 4: Size + Stars combinations for extra coverage
        size_ranges = ["<100", "100..1000", "1001..10000", ">10000"]
        for size in size_ranges:
            for stars in star_ranges[:10]:  # Focus on lower star ranges
                all_combos.append({
                    "type": "size_stars",
                    "query": f"is:public size:{size} stars:{stars} sort:updated",
                    "desc": f"Size+Stars: {size}KB, {stars} stars"
                })

        # Calculate this job's unique slice
        total_combinations = len(all_combos)
        combos_per_job = total_combinations // matrix_total
        remainder = total_combinations % matrix_total

        # Distribute remainder evenly among first jobs
        if matrix_index < remainder:
            start_idx = matrix_index * (combos_per_job + 1)
            end_idx = start_idx + combos_per_job + 1
        else:
            start_idx = matrix_index * combos_per_job + remainder
            end_idx = start_idx + combos_per_job

        # Get this job's unique combinations
        job_combos = all_combos[start_idx:end_idx]

        # Convert to SearchQuery objects
        queries = []
        for combo in job_combos[:10]:  # Limit to 10 queries per job to avoid exhaustion
            queries.append(
                SearchQuery(
                    query_string=combo["query"],
                    description=f"Job {matrix_index}: {combo['desc']}",
                    expected_results=1000,
                )
            )

        # If we have very few queries, add some broad fallbacks
        if len(queries) < 3:
            fallback_stars = star_ranges[matrix_index % len(star_ranges)]
            queries.append(
                SearchQuery(
                    query_string=f"is:public stars:{fallback_stars} sort:updated",
                    description=f"Job {matrix_index}: Fallback stars {fallback_stars}",
                    expected_results=1000,
                )
            )

        return queries


class SimpleSearchStrategy(SearchStrategy):
    """Ultra-aggressive search strategy designed to maximize repository collection
    by creating extremely granular search partitions that work around GitHub's
    1000-result API limit.
    """

    def generate_queries(
        self, matrix_index: int = 0, matrix_total: int = 1
    ) -> list[SearchQuery]:
        """Generate ultra-partitioned search queries optimized for maximum
        repository discovery."""

        if matrix_total == 1:
            return [
                SearchQuery(
                    "is:public stars:0..2 sort:updated", "Very low stars, recent", 1000
                ),
                SearchQuery("is:public stars:3..8 sort:stars", "Low stars", 1000),
                SearchQuery(
                    "is:public stars:9..25 sort:updated", "Medium-low stars", 1000
                ),
                SearchQuery("is:public stars:26..80 sort:stars", "Medium stars", 1000),
                SearchQuery(
                    "is:public stars:81..300 sort:updated", "Higher stars", 1000
                ),
            ]

        languages = [
            "javascript",
            "python",
            "java",
            "typescript",
            "go",
            "rust",
            "php",
            "c++",
            "c#",
            "ruby",
            "swift",
            "kotlin",
            "scala",
            "dart",
            "r",
            "objective-c",
            "perl",
            "haskell",
            "lua",
            "clojure",
            "f#",
            "erlang",
            "elixir",
            "crystal",
            "nim",
            "julia",
            "zig",
            "v",
            "assembly",
            "shell",
            "powershell",
            "makefile",
            "dockerfile",
            "html",
            "css",
            "scss",
            "less",
            "vue",
            "svelte",
            "coffeescript",
            "livescript",
            "ocaml",
            "racket",
            "scheme",
            "forth",
            "prolog",
            "cobol",
            "fortran",
            "pascal",
            "ada",
            "vhdl",
            "verilog",
            "matlab",
            "mathematica",
            "tex",
            "nix",
        ]

        star_ranges = [
            "0..5",
            "6..10",
            "11..15",
            "16..25",
            "26..40",
            "41..60",
            "61..90",
            "91..130",
            "131..180",
            "181..250",
            "251..350",
            "351..500",
            "501..700",
            "701..1000",
            "1001..1400",
            "1401..2000",
            "2001..3000",
            "3001..4500",
            "4501..7000",
            "7001..10000",
            "10001..15000",
            "15001..25000",
            "25001..50000",
            ">50000",
        ]

        time_ranges = [
            "2024-12-01..2025-12-31",
            "2024-11-01..2024-11-30",
            "2024-10-01..2024-10-31",
            "2024-09-01..2024-09-30",
            "2024-08-01..2024-08-31",
            "2024-07-01..2024-07-31",
            "2024-06-01..2024-06-30",
            "2024-05-01..2024-05-31",
            "2024-04-01..2024-04-30",
            "2024-03-01..2024-03-31",
            "2024-02-01..2024-02-29",
            "2024-01-01..2024-01-31",
            "2023-10-01..2023-12-31",
            "2023-07-01..2023-09-30",
            "2023-04-01..2023-06-30",
            "2023-01-01..2023-03-31",
            "2022-10-01..2022-12-31",
            "2022-07-01..2022-09-30",
            "2022-04-01..2022-06-30",
            "2022-01-01..2022-03-31",
            "2021-10-01..2021-12-31",
            "2021-07-01..2021-09-30",
            "2021-04-01..2021-06-30",
            "2021-01-01..2021-03-31",
            "2020-07-01..2020-12-31",
            "2020-01-01..2020-06-30",
            "2019-07-01..2019-12-31",
            "2019-01-01..2019-06-30",
            "2018-07-01..2018-12-31",
            "2018-01-01..2018-06-30",
            "2017-01-01..2017-12-31",
            "..2016-12-31",
        ]

        sizes = [
            "<5",
            "5..15",
            "16..50",
            "51..150",
            "151..500",
            "501..1500",
            "1501..5000",
            ">5000",
        ]

        licenses = [
            "mit",
            "apache-2.0",
            "gpl-3.0",
            "bsd-2-clause",
            "bsd-3-clause",
            "isc",
            "unlicense",
            "lgpl-2.1",
        ]

        topics = [
            "api",
            "cli",
            "framework",
            "library",
            "tool",
            "web",
            "mobile",
            "game",
            "machine-learning",
            "data",
            "security",
            "blockchain",
            "iot",
            "ai",
            "database",
            "monitoring",
            "testing",
            "automation",
            "devops",
            "cloud",
            "frontend",
            "backend",
            "fullstack",
            "microservices",
            "serverless",
            "kubernetes",
            "docker",
            "react",
            "vue",
            "angular",
        ]

        # CRITICAL FIX: Deterministic assignment without overlaps
        # Build all possible combinations
        all_combos = []

        # Priority 1: Fine-grained language + stars
        for lang in languages[:30]:  # Focus on popular languages
            for stars in star_ranges[:20]:  # Focus on lower star ranges
                all_combos.append({
                    "query": f"is:public language:{lang} stars:{stars} fork:false archived:false sort:updated",
                    "desc": f"Lang: {lang}, Stars: {stars}"
                })

        # Priority 2: Time + stars for recent repos
        for time in time_ranges[:15]:  # Recent time periods
            for stars in star_ranges[:15]:
                all_combos.append({
                    "query": f"is:public created:{time} stars:{stars} fork:false sort:updated",
                    "desc": f"Created: {time}, Stars: {stars}"
                })

        # Priority 3: Size + stars
        for size in sizes:
            for stars in star_ranges[:10]:
                all_combos.append({
                    "query": f"is:public size:{size} stars:{stars} sort:updated",
                    "desc": f"Size: {size}KB, Stars: {stars}"
                })

        # Priority 4: Topic + stars
        for topic in topics:
            for stars in star_ranges[:10]:
                all_combos.append({
                    "query": f"is:public topic:{topic} stars:{stars} fork:false sort:updated",
                    "desc": f"Topic: {topic}, Stars: {stars}"
                })

        # Priority 5: License + language + stars (very specific)
        for license in licenses[:5]:  # Common licenses
            for lang in ["javascript", "python", "java", "typescript", "go"]:
                for stars in star_ranges[:5]:
                    all_combos.append({
                        "query": f"is:public license:{license} language:{lang} stars:{stars} sort:updated",
                        "desc": f"License: {license}, Lang: {lang}, Stars: {stars}"
                    })

        # Calculate unique slice for this job
        total = len(all_combos)
        per_job = total // matrix_total
        remainder = total % matrix_total

        if matrix_index < remainder:
            start = matrix_index * (per_job + 1)
            end = start + per_job + 1
        else:
            start = matrix_index * per_job + remainder
            end = start + per_job

        # Get this job's unique combinations
        job_combos = all_combos[start:end]

        # Convert to queries (limit to prevent exhaustion)
        queries = []
        for combo in job_combos[:20]:  # More queries for aggressive strategy
            queries.append(
                SearchQuery(
                    query_string=combo["query"],
                    description=f"Job {matrix_index}: {combo['desc']}",
                    expected_results=900
                )
            )

        # Add fallback if too few queries
        if len(queries) < 5:
            # Generate simple fallback queries based on job index
            for i in range(5 - len(queries)):
                star_idx = (matrix_index + i) % len(star_ranges)
                queries.append(
                    SearchQuery(
                        query_string=f"is:public stars:{star_ranges[star_idx]} sort:updated",
                        description=f"Job {matrix_index}: Fallback {i+1}, stars {star_ranges[star_idx]}",
                        expected_results=900
                    )
                )

        return queries
