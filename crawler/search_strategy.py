"""
Optimized search strategy for GitHub repository discovery.

This module provides a simplified, more effective approach to discovering
diverse GitHub repositories while respecting API limits.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .domain import SearchQuery


@dataclass
class SearchStrategy:
    """Strategy for generating GitHub search queries."""

    def calculate_search_space(self) -> dict[str, Any]:
        """Calculate total search space coverage."""
        # Count all possible combinations (5M repos scale)
        languages = 120  # Expanded to 100+ languages
        star_ranges = 56  # Granular ranges from 0 to >95k
        time_ranges = 33  # Monthly for recent, quarterly/yearly for older
        topics = 20
        size_ranges = 8
        fork_states = 2
        archived_states = 2
        licenses = 5

        combinations = {
            "language_stars": languages * star_ranges,  # 6,720
            "time_stars": time_ranges * star_ranges,  # 1,848
            "topic_stars": topics * star_ranges,  # 1,120
            "size_stars": size_ranges * 20,  # 160
            "fork_lang_stars": fork_states * 30 * 15,  # 900 (increased)
            "archived_stars": archived_states * 30,  # 60
            "license_stars": licenses * 20,  # 100
        }

        total = sum(combinations.values())
        max_repos = total * 1000  # Each query can yield up to 1000 repos

        return {
            "total_combinations": total,
            "max_repos_theoretical": max_repos,
            "breakdown": combinations,
            "recommended_matrix_jobs": min(300, total // 50),
        }

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

        # 100+ GitHub languages for comprehensive coverage (5M repos scale)
        languages = [
            # Top 20 most popular
            "javascript",
            "python",
            "java",
            "typescript",
            "go",
            "c++",
            "ruby",
            "php",
            "c#",
            "c",
            "shell",
            "rust",
            "swift",
            "kotlin",
            "dart",
            "objective-c",
            "scala",
            "r",
            "perl",
            "haskell",
            # Next 30 common languages
            "lua",
            "julia",
            "clojure",
            "elixir",
            "f#",
            "erlang",
            "ocaml",
            "nim",
            "crystal",
            "zig",
            "powershell",
            "coffeescript",
            "groovy",
            "matlab",
            "fortran",
            "pascal",
            "d",
            "racket",
            "scheme",
            "common lisp",
            "elm",
            "purescript",
            "reason",
            "hack",
            "vala",
            "vhdl",
            "verilog",
            "ada",
            "cobol",
            "prolog",
            # Web and markup
            "html",
            "css",
            "scss",
            "less",
            "sass",
            "vue",
            "svelte",
            "markdown",
            "tex",
            "restructuredtext",
            # Data and config
            "yaml",
            "json",
            "xml",
            "toml",
            "ini",
            "dockerfile",
            "makefile",
            "cmake",
            "gradle",
            "maven",
            # Scripting and shells
            "bash",
            "zsh",
            "fish",
            "awk",
            "sed",
            "vim script",
            "emacs lisp",
            "tcl",
            "smalltalk",
            "forth",
            # Scientific and specialized
            "jupyter notebook",
            "sas",
            "stata",
            "spss",
            "igor pro",
            "labview",
            "wolfram",
            "maple",
            "gnuplot",
            "idl",
            # Mobile and game
            "gdscript",
            "qml",
            "unrealscript",
            "shaderlab",
            "hlsl",
            "glsl",
            "metal",
            "wgsl",
            "actionscript",
            "haxe",
            # Newer languages
            "v",
            "raku",
            "moonscript",
            "red",
            "pony",
            "chapel",
            "ballerina",
            "grain",
            "motoko",
            "move",
            # Functional
            "idris",
            "agda",
            "coq",
            "lean",
            "ats",
            "mercury",
            "standard ml",
            "fstar",
            "dhall",
            "nix",
            # Database
            "sql",
            "plsql",
            "plpgsql",
            "tsql",
            "mongodb",
            # Legacy but still present
            "visual basic",
            "delphi",
            "foxpro",
            "clipper",
            "rexx",
            "apl",
            "j",
            "k",
            "q",
            "mumps",
        ]

        # More granular star ranges for better coverage (5M repos)
        star_ranges = [
            "0..0",  # Exactly 0 stars (many repos)
            "1..1",  # Exactly 1 star
            "2..2",  # Exactly 2 stars
            "3..3",
            "4..4",
            "5..5",
            "6..7",
            "8..9",
            "10..12",
            "13..15",
            "16..19",
            "20..24",
            "25..29",
            "30..35",
            "36..42",
            "43..50",
            "51..60",
            "61..72",
            "73..86",
            "87..103",
            "104..124",
            "125..150",
            "151..182",
            "183..220",
            "221..267",
            "268..324",
            "325..393",
            "394..477",
            "478..580",
            "581..705",
            "706..857",
            "858..1042",
            "1043..1268",
            "1269..1543",
            "1544..1877",
            "1878..2284",
            "2285..2779",
            "2780..3380",
            "3381..4112",
            "4113..5003",
            "5004..6088",
            "6089..7408",
            "7409..9014",
            "9015..10969",
            "10970..13349",
            "13350..16243",
            "16244..19762",
            "19763..24045",
            "24046..29259",
            "29260..35607",
            "35608..43334",
            "43335..52736",
            "52737..64178",
            "64179..78106",
            "78107..95063",
            ">95063",
        ]

        # Monthly time periods for granular coverage (5M repos scale)
        time_ranges = [
            # 2025
            "2025-01-01..2025-01-31",
            # 2024 (monthly)
            "2024-12-01..2024-12-31",
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
            # 2023 (quarterly)
            "2023-10-01..2023-12-31",
            "2023-07-01..2023-09-30",
            "2023-04-01..2023-06-30",
            "2023-01-01..2023-03-31",
            # 2022 (quarterly)
            "2022-10-01..2022-12-31",
            "2022-07-01..2022-09-30",
            "2022-04-01..2022-06-30",
            "2022-01-01..2022-03-31",
            # 2021 (bi-annual)
            "2021-07-01..2021-12-31",
            "2021-01-01..2021-06-30",
            # 2020 (annual)
            "2020-01-01..2020-12-31",
            # 2019
            "2019-01-01..2019-12-31",
            # 2018
            "2018-01-01..2018-12-31",
            # 2017
            "2017-01-01..2017-12-31",
            # 2016
            "2016-01-01..2016-12-31",
            # 2015
            "2015-01-01..2015-12-31",
            # 2014 and earlier
            "2013-01-01..2014-12-31",
            "2011-01-01..2012-12-31",
            "2008-01-01..2010-12-31",
            "..2007-12-31",
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
                all_combos.append(
                    {
                        "type": "lang_stars",
                        "query": (
                            f"is:public language:{lang} stars:{stars} "
                            f"fork:false archived:false sort:updated"
                        ),
                        "desc": f"Lang+Stars: {lang}, {stars} stars",
                    }
                )

        # Priority 2: Time + Stars
        for time in time_ranges:
            for stars in star_ranges:
                all_combos.append(
                    {
                        "type": "time_stars",
                        "query": (
                            f"is:public created:{time} stars:{stars} "
                            f"fork:false sort:updated"
                        ),
                        "desc": f"Time+Stars: {time}, {stars} stars",
                    }
                )

        # Priority 3: Topic + Stars
        for topic in topics:
            for stars in star_ranges:
                all_combos.append(
                    {
                        "type": "topic_stars",
                        "query": (
                            f"is:public topic:{topic} stars:{stars} "
                            f"fork:false sort:updated"
                        ),
                        "desc": f"Topic+Stars: {topic}, {stars} stars",
                    }
                )

        # Priority 4: Size + Stars combinations for extra coverage
        size_ranges = [
            "<10",
            "10..50",
            "51..100",
            "101..500",
            "501..1000",
            "1001..5000",
            "5001..10000",
            ">10000",
        ]
        for size in size_ranges:
            for stars in star_ranges[:20]:  # Focus on lower star ranges
                all_combos.append(
                    {
                        "type": "size_stars",
                        "query": f"is:public size:{size} stars:{stars} sort:updated",
                        "desc": f"Size+Stars: {size}KB, {stars} stars",
                    }
                )

        # Priority 5: Fork status + language + stars (catch forks too)
        for is_fork in ["true", "false"]:
            for lang in languages[:30]:  # Top 30 languages
                for stars in star_ranges[:15]:  # Lower star ranges
                    all_combos.append(
                        {
                            "type": "fork_lang_stars",
                            "query": (
                                f"is:public fork:{is_fork} language:{lang} "
                                f"stars:{stars} sort:updated"
                            ),
                            "desc": f"Fork:{is_fork}, Lang:{lang}, Stars:{stars}",
                        }
                    )

        # Priority 6: Archived status + stars (include archived repos)
        for archived in ["true", "false"]:
            for stars in star_ranges[:30]:
                all_combos.append(
                    {
                        "type": "archived_stars",
                        "query": (
                            f"is:public archived:{archived} stars:{stars} sort:updated"
                        ),
                        "desc": f"Archived:{archived}, Stars:{stars}",
                    }
                )

        # Priority 7: License combinations
        licenses = ["mit", "apache-2.0", "gpl-3.0", "bsd-3-clause", "none"]
        for license in licenses:
            for stars in star_ranges[:20]:
                query = f"is:public stars:{stars} sort:updated"
                if license != "none":
                    query = f"is:public license:{license} stars:{stars} sort:updated"
                all_combos.append(
                    {
                        "type": "license_stars",
                        "query": query,
                        "desc": f"License:{license}, Stars:{stars}",
                    }
                )

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
        # Dynamic limit based on total jobs - more jobs = fewer queries each
        queries_per_job = max(5, min(50, 500 // max(1, matrix_total)))

        for combo in job_combos[:queries_per_job]:
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
    """Deterministic hour-based search strategy for maximum repository coverage.

    Each hour gets unique, non-overlapping queries using:
    - Hash-based distribution for topics
    - Round-robin for languages
    - Logarithmic star range partitioning
    - Date sampling across multiple time periods
    """

    def _get_star_ranges_for_hour(self, hour: int) -> list[str]:
        """Generate hour-specific star ranges with logarithmic distribution."""
        base_ranges = [
            (0, 0),
            (1, 1),
            (2, 5),
            (6, 10),
            (11, 20),
            (21, 50),
            (51, 100),
            (101, 200),
            (201, 500),
            (501, 1000),
            (1001, 5000),
            (5001, 10000),
            (10001, 50000),
            (50001, 1000000),
        ]

        hour_ranges = []
        for min_val, max_val in base_ranges:
            if max_val - min_val <= 24:
                # Small range - assign specific values to hours
                if min_val <= hour <= max_val:
                    hour_ranges.append(f"{hour}..{hour}")
            else:
                # Large range - divide equally among hours
                step = max(1, (max_val - min_val) // 24)
                hour_min = min_val + (hour * step)
                hour_max = min(min_val + ((hour + 1) * step) - 1, max_val)
                if hour_min <= hour_max:
                    hour_ranges.append(f"{hour_min}..{hour_max}")

        return hour_ranges

    def _get_languages_for_hour(self, hour: int) -> list[str]:
        """Get languages assigned to this hour via round-robin distribution."""
        all_languages = [
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
            "solidity",
            "groovy",
            "apex",
            "plsql",
        ]

        # Round-robin: each hour gets specific languages (2-3 per hour with 60 languages)
        return [lang for i, lang in enumerate(all_languages) if i % 24 == hour]

    def _get_topics_for_hour(self, hour: int) -> list[str]:
        """Get topics assigned to this hour via hash-based distribution."""
        all_topics = [
            "web",
            "api",
            "frontend",
            "backend",
            "database",
            "mobile",
            "android",
            "ios",
            "react",
            "vue",
            "angular",
            "django",
            "flask",
            "rails",
            "spring",
            "express",
            "laravel",
            "nodejs",
            "docker",
            "kubernetes",
            "aws",
            "azure",
            "gcp",
            "terraform",
            "machine-learning",
            "deep-learning",
            "data-science",
            "ai",
            "blockchain",
            "cryptocurrency",
            "bitcoin",
            "ethereum",
            "game",
            "unity",
            "unreal",
            "godot",
            "pygame",
            "cli",
            "terminal",
            "bash",
            "automation",
            "bot",
            "security",
            "pentesting",
            "cryptography",
            "privacy",
            "devops",
            "ci-cd",
            "monitoring",
            "logging",
            "testing",
        ]

        # Hash-based distribution ensures consistent assignment
        hour_topics = []
        for topic in all_topics:
            topic_hash = int(hashlib.md5(topic.encode()).hexdigest(), 16)
            if topic_hash % 24 == hour:
                hour_topics.append(topic)

        return hour_topics

    def generate_queries(
        self, matrix_index: int = 0, matrix_total: int = 1
    ) -> list[SearchQuery]:
        """Generate deterministic, hour-partitioned search queries.

        Each hour gets unique queries using:
        - Deterministic language assignment (round-robin)
        - Deterministic topic assignment (hash-based)
        - Hour-specific star ranges (logarithmic distribution)
        - Date sampling for broader coverage
        """
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

        # Get current hour for deterministic partitioning
        current_hour = datetime.utcnow().hour

        # Get hour-specific partitions using helper methods
        hour_languages = self._get_languages_for_hour(current_hour)
        hour_topics = self._get_topics_for_hour(current_hour)
        hour_star_ranges = self._get_star_ranges_for_hour(current_hour)

        # Generate date samples for broader coverage
        today = datetime.utcnow().date()
        date_samples = [
            today - timedelta(days=d)
            for d in [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                14,
                21,
                30,
                45,
                60,
                90,
                120,
                150,
                180,
                210,
                240,
                270,
                300,
                330,
                365,
            ]
        ]

        hour_ranges = []
        for sample_date in date_samples:
            hour_start = f"{sample_date}T{current_hour:02d}:00:00Z"
            hour_end = f"{sample_date}T{current_hour:02d}:59:59Z"
            hour_ranges.append(f"{hour_start}..{hour_end}")

        # Build all possible combinations deterministically
        all_combos = []

        # Strategy 1: Language + Stars + Date (primary)
        combo_index = 0
        for lang in hour_languages:
            for stars in hour_star_ranges:
                hour_filter = hour_ranges[combo_index % len(hour_ranges)]
                all_combos.append(
                    {
                        "query": (
                            f"is:public language:{lang} created:{hour_filter} stars:{stars} "
                            f"fork:false archived:false sort:updated"
                        ),
                        "desc": f"H{current_hour}: {lang}, {stars} stars, {hour_filter[:10]}",
                    }
                )
                combo_index += 1

        # Strategy 2: Topic + Stars + Date
        for topic in hour_topics:
            for stars in hour_star_ranges[:5]:  # Limit star ranges for topics
                hour_filter = hour_ranges[combo_index % len(hour_ranges)]
                all_combos.append(
                    {
                        "query": (
                            f"is:public topic:{topic} created:{hour_filter} stars:{stars} "
                            f"fork:false sort:updated"
                        ),
                        "desc": f"H{current_hour}: topic:{topic}, {stars} stars, {hour_filter[:10]}",
                    }
                )
                combo_index += 1

        # Strategy 3: Broad date + star queries (catch-all)
        for hour_filter in hour_ranges:
            for stars in hour_star_ranges[:3]:  # Top 3 star ranges only
                all_combos.append(
                    {
                        "query": f"is:public created:{hour_filter} stars:{stars} sort:updated",
                        "desc": f"H{current_hour}: broad, {stars} stars, {hour_filter[:10]}",
                    }
                )

        # Partition combinations across matrix jobs
        total = len(all_combos)
        per_job = max(1, total // matrix_total)
        remainder = total % matrix_total

        if matrix_index < remainder:
            start = matrix_index * (per_job + 1)
            end = start + per_job + 1
        else:
            start = matrix_index * per_job + remainder
            end = start + per_job

        job_combos = all_combos[start:end]

        # Convert to SearchQuery objects
        queries = []
        for combo in job_combos[:20]:  # Limit queries per job
            queries.append(
                SearchQuery(
                    query_string=combo["query"],
                    description=f"Job {matrix_index}: {combo['desc']}",
                    expected_results=900,
                )
            )

        # Add fallback if too few queries
        if len(queries) < 5:
            for i in range(5 - len(queries)):
                star_idx = (matrix_index + i) % len(hour_star_ranges)
                if star_idx < len(hour_star_ranges):
                    queries.append(
                        SearchQuery(
                            query_string=(
                                f"is:public stars:{hour_star_ranges[star_idx]} sort:updated"
                            ),
                            description=(
                                f"Job {matrix_index}: Fallback, stars {hour_star_ranges[star_idx]}"
                            ),
                            expected_results=900,
                        )
                    )

        return queries
