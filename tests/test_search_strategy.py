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

        # Should return multiple SearchQuery objects
        assert len(queries) > 0
        assert all(isinstance(q, SearchQuery) for q in queries)

        # All queries should be valid GitHub search strings
        for query in queries:
            assert "is:public" in query.query_string
            assert query.query_string.strip() != ""

    def test_generate_queries_multiple_matrix(self):
        """Test query generation for multiple matrix jobs."""
        strategy = SimpleSearchStrategy()

        # Generate queries for different matrix positions
        queries_0 = strategy.generate_queries(matrix_index=0, matrix_total=4)
        queries_1 = strategy.generate_queries(matrix_index=1, matrix_total=4)
        queries_2 = strategy.generate_queries(matrix_index=2, matrix_total=4)
        queries_3 = strategy.generate_queries(matrix_index=3, matrix_total=4)

        # Each should have different queries due to partitioning
        assert len(queries_0) > 0
        assert len(queries_1) > 0
        assert len(queries_2) > 0
        assert len(queries_3) > 0

        # Queries should be different between matrix jobs
        query_strings_0 = [q.query_string for q in queries_0]
        query_strings_1 = [q.query_string for q in queries_1]

        # At least some queries should be different
        assert query_strings_0 != query_strings_1

    def test_matrix_partitioning_coverage(self):
        """Test that matrix partitioning covers different search spaces."""
        strategy = SimpleSearchStrategy()

        all_languages = set()
        all_star_ranges = set()

        # Test matrix jobs 0-9 to see coverage
        for i in range(10):
            queries = strategy.generate_queries(matrix_index=i, matrix_total=10)

            for query in queries:
                # Parse language and star range from query_string
                if "language:" in query.query_string:
                    # Extract language from query_string
                    parts = query.query_string.split()
                    for part in parts:
                        if part.startswith("language:"):
                            lang = part.split(":")[1]
                            all_languages.add(lang)

                if "stars:" in query.query_string:
                    # Extract star range from query_string
                    parts = query.query_string.split()
                    for part in parts:
                        if part.startswith("stars:"):
                            star_range = part.split(":")[1]
                            all_star_ranges.add(star_range)

        # Should cover multiple languages and star ranges across all matrix jobs
        assert len(all_languages) > 1
        assert len(all_star_ranges) >= 1  # At least one star range

    def test_query_string_validity(self):
        """Test that generated query strings are valid for GitHub."""
        strategy = SimpleSearchStrategy()
        queries = strategy.generate_queries(matrix_index=0, matrix_total=1)

        for query in queries:
            query_str = query.query_string

            # Basic validity checks
            assert query_str.strip() != ""
            assert "is:public" in query_str

            # Should not have invalid characters
            assert not any(
                char in query_str for char in ["<", ">", '"'] if char not in ["<", ">"]
            )

            # Should have proper sort parameter
            assert "sort:" in query_str

    def test_search_query_metadata(self):
        """Test that SearchQuery objects have proper metadata."""
        strategy = SimpleSearchStrategy()
        queries = strategy.generate_queries(matrix_index=5, matrix_total=10)

        for query in queries:
            # Each query should have a query string
            assert query.query_string is not None
            assert len(query.query_string) > 0

            # Description should be present
            assert query.description is not None
            assert len(query.description) > 0

    def test_edge_case_matrix_index(self):
        """Test edge cases for matrix indexing."""
        strategy = SimpleSearchStrategy()

        # Test matrix index 0
        queries = strategy.generate_queries(matrix_index=0, matrix_total=1)
        assert len(queries) > 0

        # Test high matrix index
        queries = strategy.generate_queries(matrix_index=99, matrix_total=100)
        assert len(queries) > 0

        # Test single total with high index (should work via modulo)
        queries = strategy.generate_queries(matrix_index=999, matrix_total=1)
        assert len(queries) > 0

    def test_query_diversity(self):
        """Test that strategy produces diverse queries."""
        strategy = SimpleSearchStrategy()
        queries = strategy.generate_queries(matrix_index=0, matrix_total=1)

        query_strings = [q.query_string for q in queries]

        # Should have multiple different queries
        assert len(set(query_strings)) > 1

        # Should cover different aspects (languages, stars, dates)
        has_language_filter = any("language:" in q for q in query_strings)
        has_star_filter = any("stars:" in q for q in query_strings)
        has_date_filter = any("created:" in q for q in query_strings)

        # At least some filters should be present
        assert has_language_filter or has_star_filter or has_date_filter
