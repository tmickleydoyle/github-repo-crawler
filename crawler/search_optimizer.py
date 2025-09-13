"""
Optimized search strategy utilities for efficient query generation.

This module provides utilities to generate search queries more efficiently
using algorithmic approaches instead of hardcoded lists.
"""

from typing import List, Tuple


class SearchStrategyOptimizer:
    """Utility class for optimizing search strategy generation."""

    @staticmethod
    def generate_star_ranges(
        max_stars: int = 100000, num_ranges: int = 80
    ) -> List[str]:
        """
        Generate logarithmically distributed star ranges for optimal coverage.

        This creates ranges that are denser at lower star counts (where most repos are)
        and sparser at higher star counts, maximizing diversity while respecting
        GitHub's 1000-result limit per query.
        """
        ranges = []

        # Generate logarithmic progression for first part
        for i in range(min(30, num_ranges // 2)):
            start = i
            end = i
            ranges.append(f"{start}..{end}")

        # Generate exponential progression for middle part
        current = 30
        while current < max_stars and len(ranges) < num_ranges - 5:
            # Calculate range size based on current position
            range_size = max(1, int(current * 0.15))
            end = current + range_size
            ranges.append(f"{current}..{end}")
            current = end + 1

        # Add a few high-value ranges
        if len(ranges) < num_ranges:
            ranges.extend(
                [
                    f"{current}..{current + 5000}",
                    f"{current + 5001}..{current + 15000}",
                    f"{current + 15001}..{current + 50000}",
                    f">{current + 50000}",
                ]
            )

        return ranges[:num_ranges]

    @staticmethod
    def generate_time_ranges(years_back: int = 5) -> List[str]:
        """
        Generate time ranges for temporal partitioning.

        Creates monthly ranges for recent years and quarterly for older years
        to balance recency bias with historical coverage.
        """
        from datetime import datetime, timedelta

        ranges = []
        current_date = datetime.now()

        # Monthly ranges for last 2 years
        for months_back in range(24):
            end_date = current_date - timedelta(days=months_back * 30)
            start_date = end_date - timedelta(days=30)
            ranges.append(
                f"{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"
            )

        # Quarterly ranges for older years
        for quarters_back in range(8, years_back * 4):
            quarter_end = current_date - timedelta(days=quarters_back * 90)
            quarter_start = quarter_end - timedelta(days=90)
            ranges.append(
                f"{quarter_start.strftime('%Y-%m-%d')}.."
                f"{quarter_end.strftime('%Y-%m-%d')}"
            )

        # Add catch-all for very old repositories
        very_old = current_date - timedelta(days=years_back * 365)
        ranges.append(f"..{very_old.strftime('%Y-%m-%d')}")

        return ranges

    @staticmethod
    def get_popular_languages(limit: int = 50) -> List[str]:
        """
        Get list of popular programming languages for efficient partitioning.

        Ordered by popularity for optimal search coverage.
        """
        return [
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
        ][:limit]

    @staticmethod
    def get_popular_topics(limit: int = 30) -> List[str]:
        """
        Get list of popular repository topics for efficient partitioning.
        """
        return [
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
        ][:limit]

    @staticmethod
    def calculate_optimal_partition(
        matrix_index: int, matrix_total: int, total_elements: int
    ) -> Tuple[int, int]:
        """
        Calculate optimal start and end indices for matrix partitioning.

        Ensures even distribution of elements across matrix jobs while
        handling edge cases for the last job.
        """
        elements_per_job = max(1, total_elements // matrix_total)
        start_idx = matrix_index * elements_per_job

        if matrix_index == matrix_total - 1:
            # Last job gets any remaining elements
            end_idx = total_elements
        else:
            end_idx = min(start_idx + elements_per_job, total_elements)

        return start_idx, end_idx
