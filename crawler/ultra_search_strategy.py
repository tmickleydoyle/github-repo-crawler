"""
Ultra-aggressive search strategy for GitHub repository discovery.

This module provides a comprehensive approach to discovering millions of
GitHub repositories by generating hundreds of highly specific search queries
that work around GitHub's 1000-result API limit.
"""

from dataclasses import dataclass

from .domain import SearchQuery


@dataclass
class UltraSearchStrategy:
    """Ultra-aggressive search strategy designed to maximize repository collection
    by creating extremely granular search partitions that work around GitHub's
    1000-result API limit.

    This strategy generates 25-30 specific queries per matrix job to achieve
    5M+ repository discovery by exhaustively partitioning GitHub's search space.
    """

    def generate_queries(
        self, matrix_index: int = 0, matrix_total: int = 1
    ) -> list[SearchQuery]:
        """Generate ultra-partitioned search queries optimized for maximum
        repository discovery.

        For 5M repositories across 200 matrix jobs, we need ~25k repos per job.
        Each query can yield max 1000 results, so we need 25+ diverse queries per job.
        """
        if matrix_total == 1:
            return self._get_basic_queries()

        return self._get_ultra_partitioned_queries(matrix_index, matrix_total)

    def _get_basic_queries(self) -> list[SearchQuery]:
        """Generate basic queries for single-job execution."""
        return [
            SearchQuery(
                query_string="is:public stars:0..5 sort:updated",
                description="Very low star repositories, recently updated",
                expected_results=1000,
            ),
            SearchQuery(
                query_string="is:public stars:6..15 sort:stars",
                description="Low star repositories",
                expected_results=1000,
            ),
            SearchQuery(
                query_string="is:public stars:16..50 sort:updated",
                description="Medium star repositories",
                expected_results=1000,
            ),
            SearchQuery(
                query_string="is:public stars:51..150 sort:stars",
                description="Higher star repositories",
                expected_results=1000,
            ),
            SearchQuery(
                query_string="is:public stars:>150 sort:updated",
                description="Popular repositories",
                expected_results=1000,
            ),
        ]

    def _get_ultra_partitioned_queries(
        self, matrix_index: int, matrix_total: int
    ) -> list[SearchQuery]:
        """Generate ultra-partitioned queries for maximum repository discovery.

        This method generates 25-30 highly specific queries per matrix job to
        maximize repository collection and work around GitHub's 1000-result limit.
        Each query targets different segments of GitHub's repository space.
        """
        queries = []

        # Ultra-granular language + star combinations
        languages = [
            "javascript", "python", "java", "typescript", "go", "rust", "php", "c++",
            "c#", "ruby", "swift", "kotlin", "scala", "dart", "r", "objective-c",
            "perl", "haskell", "lua", "clojure", "f#", "erlang", "elixir", "crystal",
            "nim", "julia", "zig", "v", "assembly", "shell", "powershell", "makefile",
            "dockerfile", "html", "css", "scss", "less", "vue", "svelte", "coffeescript"
        ]

        # Very granular star ranges to ensure we hit 1000-result limit for each query
        ultra_fine_star_ranges = [
            "0..1", "2..3", "4..5", "6..7", "8..9", "10..12", "13..15", "16..18",
            "19..22", "23..26", "27..30", "31..35", "36..40", "41..46", "47..52",
            "53..59", "60..67", "68..76", "77..85", "86..95", "96..106", "107..118",
            "119..131", "132..145", "146..160", "161..177", "178..196", "197..217",
            "218..240", "241..265", "266..293", "294..324", "325..358", "359..395",
            "396..436", "437..481", "482..531", "532..586", "587..647", "648..714",
            "715..788", "789..869", "870..958", "959..1056", "1057..1164", "1165..1283",
            "1284..1414", "1415..1558", "1559..1717", "1718..1890", "1891..2081",
            "2082..2293", "2294..2526", "2527..2781", "2782..3061", "3062..3368",
            "3369..3707", "3708..4079", "4080..4488", "4489..4937", "4938..5432",
            "5433..5976", "5977..6574", "6575..7232", "7233..7955", "7956..8750"
        ]

        # Time-based partitions for better coverage
        time_ranges = [
            "2024-10-01..2025-12-31", "2024-07-01..2024-09-30", "2024-04-01..2024-06-30",
            "2024-01-01..2024-03-31", "2023-10-01..2023-12-31", "2023-07-01..2023-09-30",
            "2023-04-01..2023-06-30", "2023-01-01..2023-03-31", "2022-10-01..2022-12-31",
            "2022-07-01..2022-09-30", "2022-04-01..2022-06-30", "2022-01-01..2022-03-31",
            "2021-10-01..2021-12-31", "2021-07-01..2021-09-30", "2021-04-01..2021-06-30",
            "2021-01-01..2021-03-31", "2020-07-01..2020-12-31", "2020-01-01..2020-06-30",
            "2019-07-01..2019-12-31", "2019-01-01..2019-06-30", "2018-07-01..2018-12-31",
            "2018-01-01..2018-06-30", "2017-01-01..2017-12-31", "2016-01-01..2016-12-31",
            "2015-01-01..2015-12-31", "2014-01-01..2014-12-31", "2013-01-01..2013-12-31",
            "2012-01-01..2012-12-31", "2011-01-01..2011-12-31", "2008-01-01..2010-12-31"
        ]

        # Repository size ranges (in KB)
        size_ranges = [
            "0..10", "11..50", "51..100", "101..200", "201..500", "501..1000",
            "1001..2000", "2001..5000", "5001..10000", "10001..20000", "20001..50000",
            "50001..100000", "100001..200000", "200001..500000", ">500000"
        ]

        # Popular topics for better partitioning
        topics = [
            "api", "cli", "framework", "library", "tool", "web", "mobile", "game",
            "machine-learning", "data", "security", "blockchain", "iot", "ai",
            "database", "monitoring", "testing", "automation", "devops", "cloud",
            "frontend", "backend", "fullstack", "microservices", "serverless",
            "kubernetes", "docker", "react", "vue", "angular", "nodejs", "django",
            "flask", "spring", "laravel", "rails", "express", "fastapi", "nextjs",
            "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "opencv"
        ]

        # Licenses for additional partitioning
        licenses = [
            "mit", "apache-2.0", "gpl-3.0", "bsd-3-clause", "bsd-2-clause", "lgpl-3.0",
            "agpl-3.0", "mpl-2.0", "unlicense", "lgpl-2.1", "isc", "cc0-1.0"
        ]

        # Generate multiple query types for this matrix job
        query_count = 0
        max_queries_per_job = 30  # Aim for 30 queries * 1000 results = 30k repos per job

        # Strategy 1: Language + ultra-fine stars (10 queries)
        for i in range(10):
            lang_idx = (matrix_index * 10 + i) % len(languages)
            star_idx = (matrix_index * 10 + i) % len(ultra_fine_star_ranges)

            language = languages[lang_idx]
            stars = ultra_fine_star_ranges[star_idx]

            queries.append(SearchQuery(
                query_string=f"is:public language:{language} stars:{stars} fork:false sort:updated",
                description=f"Lang+Stars: {language}, {stars} stars",
                expected_results=1000,
            ))
            query_count += 1

        # Strategy 2: Time + star combinations (8 queries)
        for i in range(8):
            time_idx = (matrix_index * 8 + i) % len(time_ranges)
            star_idx = (matrix_index * 8 + i + 10) % len(ultra_fine_star_ranges)

            time_range = time_ranges[time_idx]
            stars = ultra_fine_star_ranges[star_idx]

            queries.append(SearchQuery(
                query_string=f"is:public created:{time_range} stars:{stars} sort:updated",
                description=f"Time+Stars: {time_range}, {stars} stars",
                expected_results=1000,
            ))
            query_count += 1

        # Strategy 3: Topic + star combinations (6 queries)
        for i in range(6):
            topic_idx = (matrix_index * 6 + i) % len(topics)
            star_idx = (matrix_index * 6 + i + 20) % len(ultra_fine_star_ranges)

            topic = topics[topic_idx]
            stars = ultra_fine_star_ranges[star_idx]

            queries.append(SearchQuery(
                query_string=f"is:public topic:{topic} stars:{stars} sort:updated",
                description=f"Topic+Stars: {topic}, {stars} stars",
                expected_results=1000,
            ))
            query_count += 1

        # Strategy 4: Size + time combinations (3 queries)
        for i in range(3):
            size_idx = (matrix_index * 3 + i) % len(size_ranges)
            time_idx = (matrix_index * 3 + i + 5) % len(time_ranges)

            size = size_ranges[size_idx]
            time_range = time_ranges[time_idx]

            queries.append(SearchQuery(
                query_string=f"is:public size:{size} created:{time_range} sort:updated",
                description=f"Size+Time: {size}KB, {time_range}",
                expected_results=1000,
            ))
            query_count += 1

        # Strategy 5: License + language combinations (3 queries)
        for i in range(3):
            license_idx = (matrix_index * 3 + i) % len(licenses)
            lang_idx = (matrix_index * 3 + i + 15) % len(languages)

            license_name = licenses[license_idx]
            language = languages[lang_idx]

            queries.append(SearchQuery(
                query_string=f"is:public license:{license_name} language:{language} sort:updated",
                description=f"License+Lang: {license_name}, {language}",
                expected_results=1000,
            ))
            query_count += 1

        return queries[:max_queries_per_job]
