"""
Optimized search strategy for GitHub repository discovery.

This module provides a simplified, more effective approach to discovering
diverse GitHub repositories while respecting API limits.
"""

from dataclasses import dataclass
from typing import List

from .cache import cached
from .domain import SearchQuery


@dataclass
class SearchStrategy:
    """Strategy for generating GitHub search queries."""

    def generate_queries(
        self, matrix_index: int = 0, matrix_total: int = 1
    ) -> List[SearchQuery]:
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

    def _get_basic_queries(self) -> List[SearchQuery]:
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
    ) -> List[SearchQuery]:
        """Generate queries partitioned across matrix jobs with better distribution."""

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

        partition_strategy = matrix_index % 4

        if partition_strategy == 0:
            lang_idx = matrix_index % len(languages)
            star_idx = (matrix_index // len(languages)) % len(star_ranges)

            language = languages[lang_idx]
            stars = star_ranges[star_idx]

            primary_query = f"is:public language:{language} stars:{stars} sort:updated"
            fallbacks = [
                f"is:public language:{language} stars:{stars} sort:stars",
                f"is:public stars:{stars} sort:updated",
            ]
            description = f"Lang+Stars: {language}, {stars} stars"

        elif partition_strategy == 1:
            time_idx = matrix_index % len(time_ranges)
            star_idx = (matrix_index // len(time_ranges)) % len(star_ranges)

            time_range = time_ranges[time_idx]
            stars = star_ranges[star_idx]

            primary_query = f"is:public created:{time_range} stars:{stars} sort:updated"
            fallbacks = [
                f"is:public created:{time_range} stars:{stars} sort:stars",
                f"is:public stars:{stars} created:{time_range} fork:false sort:updated",
            ]
            description = f"Time+Stars: {time_range}, {stars} stars"

        elif partition_strategy == 2:
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

            topic_idx = matrix_index % len(topics)
            star_idx = (matrix_index // len(topics)) % len(star_ranges)

            topic = topics[topic_idx]
            stars = star_ranges[star_idx]

            primary_query = f"is:public topic:{topic} stars:{stars} sort:updated"
            fallbacks = [
                f"is:public topic:{topic} sort:stars",
                f"is:public stars:{stars} sort:updated",
            ]
            description = f"Topic+Stars: {topic}, {stars} stars"

        else:
            special_searches = [
                (
                    "is:public fork:false archived:false stars:1..20 sort:updated",
                    "Active non-forks",
                ),
                ("is:public has:readme stars:1..50 sort:updated", "Documented repos"),
                ("is:public size:>100 stars:1..30 sort:updated", "Larger repos"),
                (
                    "is:public pushed:>2024-01-01 stars:1..15 sort:updated",
                    "Recently active",
                ),
                ("is:public license:mit stars:1..100 sort:updated", "MIT licensed"),
                (
                    "is:public license:apache-2.0 stars:1..80 sort:updated",
                    "Apache licensed",
                ),
                ("is:public has:issues stars:1..40 sort:updated", "With issues"),
                ("is:public has:wiki stars:1..60 sort:updated", "With documentation"),
            ]

            special_idx = matrix_index % len(special_searches)
            query, desc = special_searches[special_idx]

            primary_query = query
            fallbacks = ["is:public stars:1..25 sort:updated", "is:public sort:updated"]
            description = f"Special: {desc}"

        queries = [
            SearchQuery(
                query_string=primary_query,
                description=f"Job {matrix_index} - {description}",
                expected_results=400,
            )
        ]

        for i, fallback in enumerate(fallbacks[:2]):
            queries.append(
                SearchQuery(
                    query_string=fallback,
                    description=f"Fallback {i + 1} for job {matrix_index}",
                    expected_results=300,
                )
            )

        return queries


class OptimizedSearchStrategy(SearchStrategy):
    """
    Highly optimized search strategy using algorithmic generation.

    This strategy uses mathematical functions to generate diverse search queries
    instead of hardcoded lists, making it more efficient and maintainable.
    """

    def __init__(self):
        from .search_optimizer import SearchStrategyOptimizer

        self.optimizer = SearchStrategyOptimizer()

        # Cache generated elements for performance
        self._languages = None
        self._star_ranges = None
        self._time_ranges = None
        self._topics = None

    @property
    def languages(self) -> List[str]:
        """Get cached list of popular languages."""
        if self._languages is None:
            self._languages = self.optimizer.get_popular_languages(50)
        return self._languages

    @property
    def star_ranges(self) -> List[str]:
        """Get cached list of optimized star ranges."""
        if self._star_ranges is None:
            self._star_ranges = self.optimizer.generate_star_ranges(100000, 80)
        return self._star_ranges

    @property
    def time_ranges(self) -> List[str]:
        """Get cached list of time ranges."""
        if self._time_ranges is None:
            self._time_ranges = self.optimizer.generate_time_ranges(5)
        return self._time_ranges

    @property
    def topics(self) -> List[str]:
        """Get cached list of popular topics."""
        if self._topics is None:
            self._topics = self.optimizer.get_popular_topics(30)
        return self._topics

    @cached(ttl=600)  # Cache for 10 minutes
    def generate_queries(
        self, matrix_index: int = 0, matrix_total: int = 1
    ) -> List[SearchQuery]:
        """
        Generate optimized search queries using algorithmic partitioning.

        Uses mathematical distribution instead of hardcoded lists for better
        performance and maintainability. Results are cached for efficiency.
        """
        if matrix_total == 1:
            return self._get_basic_optimized_queries()

        return self._get_optimized_partitioned_queries(matrix_index, matrix_total)

    def _get_basic_optimized_queries(self) -> List[SearchQuery]:
        """Generate basic queries for single-job execution using optimization."""
        queries = []

        # Use first few star ranges for basic queries
        for i, star_range in enumerate(self.star_ranges[:5]):
            sort_order = "updated" if i % 2 == 0 else "stars"
            queries.append(
                SearchQuery(
                    query_string=f"is:public stars:{star_range} sort:{sort_order}",
                    description=f"Optimized range {star_range}, sorted by {sort_order}",
                    expected_results=800,
                )
            )

        return queries

    def _get_optimized_partitioned_queries(
        self, matrix_index: int, matrix_total: int
    ) -> List[SearchQuery]:
        """Generate optimally partitioned queries using algorithmic distribution."""

        # Use modulo-based strategy selection for even distribution
        partition_strategy = matrix_index % 4

        if partition_strategy == 0:
            return self._generate_language_star_queries(matrix_index, matrix_total)
        elif partition_strategy == 1:
            return self._generate_time_star_queries(matrix_index, matrix_total)
        elif partition_strategy == 2:
            return self._generate_topic_queries(matrix_index, matrix_total)
        else:
            return self._generate_special_queries(matrix_index, matrix_total)

    def _generate_language_star_queries(
        self, matrix_index: int, matrix_total: int
    ) -> List[SearchQuery]:
        """Generate language + star range queries using optimal partitioning."""
        # Calculate partitions using optimizer
        lang_start, lang_end = self.optimizer.calculate_optimal_partition(
            matrix_index, matrix_total, len(self.languages)
        )
        star_start, star_end = self.optimizer.calculate_optimal_partition(
            matrix_index, matrix_total, len(self.star_ranges)
        )

        queries = []

        # Use cycling to ensure good distribution
        lang_idx = (matrix_index * 3) % len(self.languages)
        star_idx = (matrix_index * 2) % len(self.star_ranges)

        language = self.languages[lang_idx]
        stars = self.star_ranges[star_idx]

        # Primary query with language + stars
        primary_query = (
            f"is:public language:{language} stars:{stars} fork:false sort:updated"
        )
        queries.append(
            SearchQuery(
                primary_query,
                f"Optimized job {matrix_index}: {language}, {stars} stars",
                900,
            )
        )

        # Fallback without language constraint
        fallback_query = f"is:public stars:{stars} sort:stars"
        queries.append(
            SearchQuery(
                fallback_query, f"Fallback for job {matrix_index}: {stars} stars", 800
            )
        )

        return queries

    def _generate_time_star_queries(
        self, matrix_index: int, matrix_total: int
    ) -> List[SearchQuery]:
        """Generate time + star range queries using optimal partitioning."""
        time_idx = matrix_index % len(self.time_ranges)
        star_idx = (matrix_index * 3) % len(self.star_ranges)

        time_range = self.time_ranges[time_idx]
        stars = self.star_ranges[star_idx]

        queries = []

        primary_query = f"is:public created:{time_range} stars:{stars} sort:updated"
        queries.append(
            SearchQuery(
                primary_query,
                f"Time-based job {matrix_index}: {time_range}, {stars} stars",
                900,
            )
        )

        # Fallback with pushed date instead of created
        fallback_query = f"is:public pushed:{time_range} stars:{stars} sort:stars"
        queries.append(
            SearchQuery(fallback_query, f"Time fallback for job {matrix_index}", 800)
        )

        return queries

    def _generate_topic_queries(
        self, matrix_index: int, matrix_total: int
    ) -> List[SearchQuery]:
        """Generate topic-based queries using optimal partitioning."""
        topic_idx = matrix_index % len(self.topics)
        star_idx = (matrix_index * 2) % len(self.star_ranges)

        topic = self.topics[topic_idx]
        stars = self.star_ranges[star_idx]

        queries = []

        primary_query = f"is:public topic:{topic} stars:{stars} fork:false sort:updated"
        queries.append(
            SearchQuery(
                primary_query, f"Topic job {matrix_index}: {topic}, {stars} stars", 900
            )
        )

        return queries

    def _generate_special_queries(
        self, matrix_index: int, matrix_total: int
    ) -> List[SearchQuery]:
        """Generate special search patterns using algorithmic selection."""
        # Use matrix index to deterministically select special patterns
        special_patterns = [
            (
                "is:public fork:false archived:false has:readme stars:{} sort:updated",
                "Active documented repos",
            ),
            ("is:public pushed:>2024-01-01 stars:{} sort:updated", "Recently active"),
            ("is:public license:mit stars:{} sort:updated", "MIT licensed"),
            (
                "is:public has:issues has:wiki stars:{} sort:updated",
                "With issues and wiki",
            ),
            (
                "is:public good-first-issues:>0 stars:{} sort:updated",
                "Good first issues",
            ),
            ("is:public size:<100 stars:{} sort:updated", "Small repositories"),
            ("is:public template:true stars:{} sort:updated", "Template repositories"),
            ("is:public mirror:false stars:{} sort:updated", "Non-mirror repositories"),
        ]

        pattern_idx = matrix_index % len(special_patterns)
        star_idx = matrix_index % len(self.star_ranges)

        pattern, description = special_patterns[pattern_idx]
        stars = self.star_ranges[star_idx]

        query = pattern.format(stars)

        return [
            SearchQuery(
                query, f"Special {matrix_index}: {description}, {stars} stars", 900
            )
        ]
