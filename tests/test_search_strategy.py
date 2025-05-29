"""
Unit tests for search strategy implementation.

These tests verify that:
1. Search queries are generated correctly
2. Matrix partitioning works as expected
3. Search strategies handle edge cases properly
4. Query optimization produces valid GitHub search strings
"""

from crawler.search_strategy import SimpleSearchStrategy
from crawler.domain import SearchQuery


class TestSimpleSearchStrategy:
    """Test SimpleSearchStrategy implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.strategy = SimpleSearchStrategy()

    def test_strategy_initialization(self):
        """Test strategy initializes correctly."""
        strategy = SimpleSearchStrategy()
        assert strategy is not None
        assert hasattr(strategy, "generate_queries")

    def test_generate_queries_single_matrix(self):
        """Test query generation for single matrix job."""
        strategy = SimpleSearchStrategy()
        queries = strategy.generate_queries(matrix_index=0, matrix_total=1)

        assert len(queries) > 0
        assert all(isinstance(q, SearchQuery) for q in queries)

        for query in queries:
            assert "is:public" in query.query_string
            assert query.query_string.strip() != ""

    def test_generate_queries_multiple_matrix(self):
        """Test query generation for multiple matrix jobs."""
        strategy = SimpleSearchStrategy()

        queries_0 = strategy.generate_queries(matrix_index=0, matrix_total=4)
        queries_1 = strategy.generate_queries(matrix_index=1, matrix_total=4)
        queries_2 = strategy.generate_queries(matrix_index=2, matrix_total=4)
        queries_3 = strategy.generate_queries(matrix_index=3, matrix_total=4)

        assert len(queries_0) > 0
        assert len(queries_1) > 0
        assert len(queries_2) > 0
        assert len(queries_3) > 0

        query_strings_0 = [q.query_string for q in queries_0]
        query_strings_1 = [q.query_string for q in queries_1]

        assert query_strings_0 != query_strings_1

    def test_matrix_partitioning_coverage(self):
        """Test that matrix partitioning covers different search spaces."""
        strategy = SimpleSearchStrategy()

        all_languages = set()
        all_star_ranges = set()

        for i in range(10):
            queries = strategy.generate_queries(matrix_index=i, matrix_total=10)

            for query in queries:
                if "language:" in query.query_string:
                    parts = query.query_string.split()
                    for part in parts:
                        if part.startswith("language:"):
                            lang = part.split(":")[1]
                            all_languages.add(lang)

                if "stars:" in query.query_string:
                    parts = query.query_string.split()
                    for part in parts:
                        if part.startswith("stars:"):
                            star_range = part.split(":")[1]
                            all_star_ranges.add(star_range)

        assert len(all_languages) > 1
        assert len(all_star_ranges) >= 1

    def test_query_string_validity(self):
        """Test that generated query strings are valid for GitHub."""
        strategy = SimpleSearchStrategy()
        queries = strategy.generate_queries(matrix_index=0, matrix_total=1)

        for query in queries:
            query_str = query.query_string

            assert query_str.strip() != ""
            assert "is:public" in query_str

            assert not any(
                char in query_str for char in ["<", ">", '"'] if char not in ["<", ">"]
            )

            assert "sort:" in query_str

    def test_search_query_metadata(self):
        """Test that SearchQuery objects have proper metadata."""
        strategy = SimpleSearchStrategy()
        queries = strategy.generate_queries(matrix_index=5, matrix_total=10)

        for query in queries:
            assert query.query_string is not None
            assert len(query.query_string) > 0

            assert query.description is not None
            assert len(query.description) > 0

    def test_edge_case_matrix_index(self):
        """Test edge cases for matrix indexing."""
        strategy = SimpleSearchStrategy()

        queries = strategy.generate_queries(matrix_index=0, matrix_total=1)
        assert len(queries) > 0

        queries = strategy.generate_queries(matrix_index=99, matrix_total=100)
        assert len(queries) > 0

        queries = strategy.generate_queries(matrix_index=999, matrix_total=1)
        assert len(queries) > 0

    def test_query_diversity(self):
        """Test that strategy produces diverse queries."""
        strategy = SimpleSearchStrategy()
        queries = strategy.generate_queries(matrix_index=0, matrix_total=1)

        query_strings = [q.query_string for q in queries]

        assert len(set(query_strings)) > 1

        has_language_filter = any("language:" in q for q in query_strings)
        has_star_filter = any("stars:" in q for q in query_strings)
        has_date_filter = any("created:" in q for q in query_strings)

        assert has_language_filter or has_star_filter or has_date_filter
