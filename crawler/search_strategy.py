"""
Optimized search strategy for GitHub repository discovery.

This module provides a simplified, more effective approach to discovering
diverse GitHub repositories while respecting API limits.
"""

from typing import List
from dataclasses import dataclass
from .domain import SearchQuery
from .cache import cached


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
            queries.append(SearchQuery(
                query_string=f"is:public stars:{star_range} sort:{sort_order}",
                description=f"Optimized range {star_range}, sorted by {sort_order}",
                expected_results=800,
            ))
        
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
    
    def _generate_language_star_queries(self, matrix_index: int, matrix_total: int) -> List[SearchQuery]:
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
        primary_query = f"is:public language:{language} stars:{stars} fork:false sort:updated"
        queries.append(SearchQuery(
            primary_query,
            f"Optimized job {matrix_index}: {language}, {stars} stars",
            900
        ))
        
        # Fallback without language constraint
        fallback_query = f"is:public stars:{stars} sort:stars"
        queries.append(SearchQuery(
            fallback_query,
            f"Fallback for job {matrix_index}: {stars} stars",
            800
        ))
        
        return queries
    
    def _generate_time_star_queries(self, matrix_index: int, matrix_total: int) -> List[SearchQuery]:
        """Generate time + star range queries using optimal partitioning."""
        time_idx = matrix_index % len(self.time_ranges)
        star_idx = (matrix_index * 3) % len(self.star_ranges)
        
        time_range = self.time_ranges[time_idx]
        stars = self.star_ranges[star_idx]
        
        queries = []
        
        primary_query = f"is:public created:{time_range} stars:{stars} sort:updated"
        queries.append(SearchQuery(
            primary_query,
            f"Time-based job {matrix_index}: {time_range}, {stars} stars",
            900
        ))
        
        # Fallback with pushed date instead of created
        fallback_query = f"is:public pushed:{time_range} stars:{stars} sort:stars"
        queries.append(SearchQuery(
            fallback_query,
            f"Time fallback for job {matrix_index}",
            800
        ))
        
        return queries
    
    def _generate_topic_queries(self, matrix_index: int, matrix_total: int) -> List[SearchQuery]:
        """Generate topic-based queries using optimal partitioning."""
        topic_idx = matrix_index % len(self.topics)
        star_idx = (matrix_index * 2) % len(self.star_ranges)
        
        topic = self.topics[topic_idx]
        stars = self.star_ranges[star_idx]
        
        queries = []
        
        primary_query = f"is:public topic:{topic} stars:{stars} fork:false sort:updated"
        queries.append(SearchQuery(
            primary_query,
            f"Topic job {matrix_index}: {topic}, {stars} stars",
            900
        ))
        
        return queries
    
    def _generate_special_queries(self, matrix_index: int, matrix_total: int) -> List[SearchQuery]:
        """Generate special search patterns using algorithmic selection."""
        # Use matrix index to deterministically select special patterns
        special_patterns = [
            ("is:public fork:false archived:false has:readme stars:{} sort:updated", "Active documented repos"),
            ("is:public pushed:>2024-01-01 stars:{} sort:updated", "Recently active"),
            ("is:public license:mit stars:{} sort:updated", "MIT licensed"),
            ("is:public has:issues has:wiki stars:{} sort:updated", "With issues and wiki"),
            ("is:public good-first-issues:>0 stars:{} sort:updated", "Good first issues"),
            ("is:public size:<100 stars:{} sort:updated", "Small repositories"),
            ("is:public template:true stars:{} sort:updated", "Template repositories"),
            ("is:public mirror:false stars:{} sort:updated", "Non-mirror repositories"),
        ]
        
        pattern_idx = matrix_index % len(special_patterns)
        star_idx = matrix_index % len(self.star_ranges)
        
        pattern, description = special_patterns[pattern_idx]
        stars = self.star_ranges[star_idx]
        
        query = pattern.format(stars)
        
        return [SearchQuery(
            query,
            f"Special {matrix_index}: {description}, {stars} stars",
            900
        )]
    """Ultra-aggressive search strategy designed to maximize repository collection
    by creating extremely granular search partitions that work around GitHub's
    1000-result API limit.
    """

    def generate_queries(
        self, matrix_index: int = 0, matrix_total: int = 1
    ) -> List[SearchQuery]:
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
            "0..0",
            "1..1",
            "2..2",
            "3..3",
            "4..4",
            "5..5",
            "6..6",
            "7..7",
            "8..8",
            "9..9",
            "10..10",
            "11..11",
            "12..12",
            "13..13",
            "14..14",
            "15..15",
            "16..16",
            "17..17",
            "18..18",
            "19..19",
            "20..20",
            "21..21",
            "22..22",
            "23..23",
            "24..24",
            "25..25",
            "26..27",
            "28..29",
            "30..31",
            "32..34",
            "35..37",
            "38..41",
            "42..45",
            "46..50",
            "51..55",
            "56..62",
            "63..70",
            "71..79",
            "80..89",
            "90..100",
            "101..115",
            "116..132",
            "133..152",
            "153..175",
            "176..202",
            "203..233",
            "234..270",
            "271..313",
            "314..364",
            "365..425",
            "426..497",
            "498..582",
            "583..682",
            "683..800",
            "801..938",
            "939..1100",
            "1101..1290",
            "1291..1515",
            "1516..1780",
            "1781..2090",
            "2091..2457",
            "2458..2890",
            "2891..3400",
            "3401..4000",
            "4001..4700",
            "4701..5520",
            "5521..6490",
            "6491..7630",
            "7631..8970",
            "8971..10550",
            "10551..12410",
            "12411..14600",
            "14601..17160",
            "17161..20170",
            "20171..23700",
            "23701..27880",
            "27881..32790",
            "32791..38560",
            "38561..45350",
            ">45350",
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

        partition_strategy = matrix_index % 6

        if partition_strategy == 0:
            lang_idx = matrix_index % len(languages)
            star_idx = (matrix_index // len(languages)) % len(star_ranges)

            language = languages[lang_idx]
            stars = star_ranges[star_idx]

            primary_query = (
                f"is:public language:{language} stars:{stars} "
                f"fork:false archived:false sort:updated"
            )

            queries = [
                SearchQuery(
                    primary_query, f"Lang+Stars: {language}, {stars} stars", 900
                ),
                SearchQuery(
                    f"is:public language:{language} stars:{stars} sort:stars",
                    f"Fallback: {language}, {stars} stars",
                    800,
                ),
            ]

        elif partition_strategy == 1:
            time_idx = matrix_index % len(time_ranges)
            star_idx = (matrix_index // len(time_ranges)) % len(star_ranges)

            time_range = time_ranges[time_idx]
            stars = star_ranges[star_idx]

            primary_query = (
                f"is:public created:{time_range} stars:{stars} fork:false sort:updated"
            )

            queries = [
                SearchQuery(
                    primary_query, f"Time+Stars: {time_range}, {stars} stars", 900
                ),
                SearchQuery(
                    f"is:public created:{time_range} stars:{stars} sort:stars",
                    f"Time fallback: {time_range}",
                    800,
                ),
            ]

        elif partition_strategy == 2:
            size_idx = matrix_index % len(sizes)
            lang_idx = (matrix_index // len(sizes)) % len(languages)
            star_idx = (matrix_index // (len(sizes) * len(languages))) % len(
                star_ranges
            )

            size = sizes[size_idx]
            language = languages[lang_idx]
            stars = star_ranges[star_idx]

            primary_query = (
                f"is:public size:{size} language:{language} stars:{stars} sort:updated"
            )

            queries = [
                SearchQuery(
                    primary_query,
                    f"Size+Lang+Stars: {size}KB, {language}, {stars} stars",
                    900,
                ),
                SearchQuery(
                    f"is:public size:{size} stars:{stars} sort:updated",
                    f"Size fallback: {size}KB",
                    800,
                ),
            ]

        elif partition_strategy == 3:
            topic_idx = matrix_index % len(topics)
            star_idx = (matrix_index // len(topics)) % len(star_ranges)

            topic = topics[topic_idx]
            stars = star_ranges[star_idx]

            primary_query = (
                f"is:public topic:{topic} stars:{stars} fork:false sort:updated"
            )

            queries = [
                SearchQuery(primary_query, f"Topic+Stars: {topic}, {stars} stars", 900),
                SearchQuery(
                    f"is:public topic:{topic} sort:stars",
                    f"Topic fallback: {topic}",
                    800,
                ),
            ]

        elif partition_strategy == 4:
            license_idx = matrix_index % len(licenses)
            lang_idx = (matrix_index // len(licenses)) % len(languages)
            star_idx = (matrix_index // (len(licenses) * len(languages))) % len(
                star_ranges
            )

            license_type = licenses[license_idx]
            language = languages[lang_idx]
            stars = star_ranges[star_idx]

            primary_query = (
                f"is:public license:{license_type} language:{language} "
                f"stars:{stars} sort:updated"
            )

            queries = [
                SearchQuery(
                    primary_query,
                    f"License+Lang: {license_type}, {language}, {stars} stars",
                    900,
                ),
                SearchQuery(
                    f"is:public license:{license_type} stars:{stars} sort:stars",
                    f"License fallback: {license_type}",
                    800,
                ),
            ]

        else:
            special_searches = [
                (
                    "is:public fork:false archived:false has:readme "
                    "stars:0..1 sort:updated",
                    "Active non-forks, documented, 0-1 stars",
                ),
                (
                    "is:public fork:false archived:false has:readme "
                    "stars:2..3 sort:updated",
                    "Active non-forks, documented, 2-3 stars",
                ),
                (
                    "is:public fork:false archived:false has:readme "
                    "stars:4..5 sort:updated",
                    "Active non-forks, documented, 4-5 stars",
                ),
                (
                    "is:public fork:false archived:false has:readme "
                    "stars:6..8 sort:updated",
                    "Active non-forks, documented, 6-8 stars",
                ),
                (
                    "is:public fork:false archived:false has:readme "
                    "stars:9..12 sort:updated",
                    "Active non-forks, documented, 9-12 stars",
                ),
                (
                    "is:public pushed:>2024-06-01 stars:0..2 sort:updated",
                    "Recently pushed, 0-2 stars",
                ),
                (
                    "is:public pushed:>2024-06-01 stars:3..5 sort:updated",
                    "Recently pushed, 3-5 stars",
                ),
                (
                    "is:public pushed:>2024-06-01 stars:6..10 sort:updated",
                    "Recently pushed, 6-10 stars",
                ),
                (
                    "is:public has:issues has:wiki stars:1..15 sort:updated",
                    "With issues and wiki, 1-15 stars",
                ),
                (
                    "is:public good-first-issues:>0 stars:1..25 sort:updated",
                    "Good first issues, 1-25 stars",
                ),
                (
                    "is:public help-wanted-issues:>0 stars:1..20 sort:updated",
                    "Help wanted issues, 1-20 stars",
                ),
                (
                    "is:public size:<100 stars:1..8 sort:updated",
                    "Small repos, 1-8 stars",
                ),
                (
                    "is:public size:100..1000 stars:1..12 sort:updated",
                    "Medium repos, 1-12 stars",
                ),
                (
                    "is:public template:true stars:1..50 sort:updated",
                    "Template repos, 1-50 stars",
                ),
                (
                    "is:public mirror:false stars:0..3 sort:updated",
                    "Non-mirror repos, 0-3 stars",
                ),
            ]

            special_idx = matrix_index % len(special_searches)
            query, description = special_searches[special_idx]

            queries = [
                SearchQuery(query, f"Special {matrix_index}: {description}", 900)
            ]

        return queries
