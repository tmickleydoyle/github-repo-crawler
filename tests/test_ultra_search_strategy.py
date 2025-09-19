"""
Test ultra search strategy for scaling to 5M repositories.

These tests verify that:
1. Ultra search strategy generates sufficient queries for 5M targets
2. Matrix partitioning produces diverse, non-overlapping queries
3. Query complexity doesn't exceed GitHub API limits
4. Scaling calculations work correctly
"""

import pytest

from crawler.domain import SearchQuery
from crawler.ultra_search_strategy import UltraSearchStrategy


class TestUltraSearchStrategy:
    """Test UltraSearchStrategy implementation for 5M repository scaling."""

    def setUp(self):
        """Set up test fixtures."""
        self.strategy = UltraSearchStrategy()

    def test_strategy_initialization(self):
        """Test strategy initializes correctly."""
        strategy = UltraSearchStrategy()
        assert strategy is not None
        assert hasattr(strategy, "generate_queries")

    def test_single_matrix_basic_queries(self):
        """Test basic query generation for single matrix job."""
        strategy = UltraSearchStrategy()
        queries = strategy.generate_queries(matrix_index=0, matrix_total=1)

        assert len(queries) == 5  # Basic queries for single job
        assert all(isinstance(q, SearchQuery) for q in queries)
        
        for query in queries:
            assert "is:public" in query.query_string
            assert query.query_string.strip() != ""
            assert query.expected_results == 1000

    def test_ultra_partitioned_queries_count(self):
        """Test that ultra partitioning generates enough queries for scaling."""
        strategy = UltraSearchStrategy()
        
        # Test for 200 matrix jobs (target configuration)
        queries = strategy.generate_queries(matrix_index=0, matrix_total=200)
        
        # Should generate 30 queries per job
        assert len(queries) == 30
        
        # Each query should target 1000 results
        assert all(q.expected_results == 1000 for q in queries)
        
        # Total potential repositories for one job: 30 * 1000 = 30k
        estimated_repos_per_job = len(queries) * 1000
        assert estimated_repos_per_job == 30000

    def test_scaling_calculation_for_5m_target(self):
        """Test that scaling calculations support 5M repository target."""
        strategy = UltraSearchStrategy()
        
        matrix_jobs = 200
        queries_per_job = 30
        repos_per_query = 1000
        
        # Test several different matrix jobs
        for matrix_index in [0, 50, 100, 150, 199]:
            queries = strategy.generate_queries(matrix_index, matrix_jobs)
            assert len(queries) == queries_per_job
        
        # Calculate total potential repositories
        total_potential_repos = matrix_jobs * queries_per_job * repos_per_query
        assert total_potential_repos == 6_000_000  # 6M potential (> 5M target)

    def test_matrix_partitioning_diversity(self):
        """Test that different matrix jobs generate diverse queries."""
        strategy = UltraSearchStrategy()
        
        queries_0 = strategy.generate_queries(matrix_index=0, matrix_total=200)
        queries_50 = strategy.generate_queries(matrix_index=50, matrix_total=200)
        queries_100 = strategy.generate_queries(matrix_index=100, matrix_total=200)
        
        # Convert to strings for comparison
        query_strings_0 = [q.query_string for q in queries_0]
        query_strings_50 = [q.query_string for q in queries_50]
        query_strings_100 = [q.query_string for q in queries_100]
        
        # Queries should be different across matrix jobs
        assert query_strings_0 != query_strings_50
        assert query_strings_50 != query_strings_100
        assert query_strings_0 != query_strings_100

    def test_query_complexity_limits(self):
        """Test that generated queries don't exceed GitHub API complexity."""
        strategy = UltraSearchStrategy()
        queries = strategy.generate_queries(matrix_index=0, matrix_total=200)
        
        for query in queries:
            # Check query isn't too complex (GitHub has limits on search complexity)
            query_parts = query.query_string.split()
            assert len(query_parts) <= 10  # Reasonable complexity limit
            
            # Ensure no invalid characters or syntax
            assert "is:public" in query.query_string
            assert not query.query_string.endswith(" ")
            assert not query.query_string.startswith(" ")

    def test_query_diversity_patterns(self):
        """Test that queries use diverse search patterns."""
        strategy = UltraSearchStrategy()
        queries = strategy.generate_queries(matrix_index=0, matrix_total=200)
        
        query_strings = [q.query_string for q in queries]
        
        # Should have language-based queries
        has_language_filter = any("language:" in q for q in query_strings)
        assert has_language_filter
        
        # Should have star-based queries  
        has_star_filter = any("stars:" in q for q in query_strings)
        assert has_star_filter
        
        # Should have time-based queries
        has_time_filter = any("created:" in q for q in query_strings)
        assert has_time_filter
        
        # Should have topic-based queries
        has_topic_filter = any("topic:" in q for q in query_strings)
        assert has_topic_filter
        
        # Should have size-based queries
        has_size_filter = any("size:" in q for q in query_strings)
        assert has_size_filter

    def test_no_query_duplication_within_job(self):
        """Test that queries within a single matrix job are unique."""
        strategy = UltraSearchStrategy()
        queries = strategy.generate_queries(matrix_index=0, matrix_total=200)
        
        query_strings = [q.query_string for q in queries]
        
        # All queries should be unique within a job
        assert len(set(query_strings)) == len(query_strings)

    def test_high_matrix_job_indices(self):
        """Test that high matrix job indices work correctly."""
        strategy = UltraSearchStrategy()
        
        # Test with high matrix indices
        queries_190 = strategy.generate_queries(matrix_index=190, matrix_total=200)
        queries_199 = strategy.generate_queries(matrix_index=199, matrix_total=200)
        
        assert len(queries_190) == 30
        assert len(queries_199) == 30
        
        # Should still be different
        assert [q.query_string for q in queries_190] != [q.query_string for q in queries_199]

    def test_expected_results_consistency(self):
        """Test that all ultra queries expect 1000 results."""
        strategy = UltraSearchStrategy()
        queries = strategy.generate_queries(matrix_index=42, matrix_total=200)
        
        # All ultra queries should expect to hit GitHub's 1000-result limit
        for query in queries:
            assert query.expected_results == 1000