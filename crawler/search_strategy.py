"""
Optimized search strategy for GitHub repository discovery.

This module provides a simplified, more effective approach to discovering
diverse GitHub repositories while respecting API limits.
"""

from typing import List
from dataclasses import dataclass
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
            # Single job mode - use basic queries
            return self._get_basic_queries()

        # Multi-job mode - partition by primary dimensions
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
        """Generate queries partitioned across matrix jobs."""

        # Primary languages for good coverage
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
            "html",
            "css",
            "shell",
            "c",
            "dart",
            "r",
            "objective-c",
        ]

        # Star ranges with good repository distribution
        star_ranges = [
            "0..1",
            "2..5",
            "6..15",
            "16..50",
            "51..150",
            "151..500",
            "501..1500",
            "1501..5000",
            ">5000",
        ]

        # Time-based partitioning for diversity
        time_ranges = [
            "2024-01-01..2025-12-31",  # Very recent
            "2023-01-01..2023-12-31",  # Recent
            "2022-01-01..2022-12-31",  # Somewhat recent
            "2020-01-01..2021-12-31",  # Older but active
            "..2019-12-31",  # Historical
        ]

        # Calculate partition indices
        lang_partition = matrix_index % len(languages)
        star_partition = (matrix_index // len(languages)) % len(star_ranges)
        time_partition = (matrix_index // (len(languages) * len(star_ranges))) % len(
            time_ranges
        )

        selected_lang = languages[lang_partition]
        selected_stars = star_ranges[star_partition]
        selected_time = time_ranges[time_partition]

        # Generate primary query
        primary_query = (
            f"is:public language:{selected_lang} stars:{selected_stars} "
            f"created:{selected_time} sort:updated"
        )

        # Generate fallback queries for better coverage
        fallback_queries = [
            f"is:public language:{selected_lang} stars:{selected_stars} sort:stars",
            f"is:public stars:{selected_stars} created:{selected_time} sort:updated",
            f"is:public language:{selected_lang} created:{selected_time} sort:stars",
        ]

        queries = [
            SearchQuery(
                query_string=primary_query,
                description=(
                    f"Primary: {selected_lang}, {selected_stars} stars, "
                    f"{selected_time}"
                ),
                expected_results=500,
            )
        ]

        # Add fallback queries
        for i, fallback in enumerate(fallback_queries):
            queries.append(
                SearchQuery(
                    query_string=fallback,
                    description=f"Fallback {i + 1}: broader search for coverage",
                    expected_results=200,
                )
            )

        return queries


class SimpleSearchStrategy(SearchStrategy):
    """Simplified search strategy focusing on reliability over complexity."""

    def generate_queries(
        self, matrix_index: int = 0, matrix_total: int = 1
    ) -> List[SearchQuery]:
        """Generate simple, reliable search queries."""

        if matrix_total == 1:
            return [
                SearchQuery(
                    "is:public stars:0..10 sort:updated",
                    "Low stars, recent",
                    2000,
                ),
                SearchQuery("is:public stars:11..100 sort:stars", "Medium stars", 2000),
                SearchQuery(
                    "is:public stars:>100 sort:updated",
                    "High stars, recent",
                    1000,
                ),
            ]

        # For matrix jobs, use simple partitioning
        base_queries = [
            "is:public language:javascript stars:1..50",
            "is:public language:python stars:1..50",
            "is:public language:java stars:1..50",
            "is:public language:typescript stars:1..50",
            "is:public language:go stars:1..50",
            "is:public language:rust stars:1..50",
            "is:public language:php stars:1..50",
            "is:public language:c++ stars:1..50",
            "is:public language:c# stars:1..50",
            "is:public language:ruby stars:1..50",
            "is:public stars:51..200",
            "is:public stars:201..1000",
            "is:public stars:>1000 sort:stars",
            "is:public created:2024-01-01..2025-12-31 stars:1..20",
            "is:public created:2023-01-01..2023-12-31 stars:1..20",
        ]

        # Cycle through base queries based on matrix index
        query_index = matrix_index % len(base_queries)
        selected_query = base_queries[query_index]

        return [
            SearchQuery(
                query_string=f"{selected_query} sort:updated",
                description=f"Matrix job {matrix_index}: {selected_query}",
                expected_results=1000,
            ),
            SearchQuery(
                query_string=f"{selected_query} sort:stars",
                description=f"Fallback for job {matrix_index}",
                expected_results=500,
            ),
        ]
