"""
Unit tests for domain models and anti-corruption layer.

These tests verify that:
1. Domain models are immutable and properly validated
2. Anti-corruption layer correctly transforms API responses
3. Custom exceptions work as expected
4. Repository statistics are calculated correctly
"""

import pytest
from datetime import datetime
from crawler.domain import (
    Repository,
    RepositoryStats,
    SearchQuery,
    CrawlResult,
    transform_github_response,
    create_repository_stats,
    RateLimitError,
    AuthenticationError,
    SearchExhaustedError,
    ApiError,
)


class TestRepository:
    """Test Repository domain model."""

    def test_repository_creation(self):
        """Test basic repository creation."""
        repo = Repository(
            id=123,
            name="test-repo",
            owner="test-user",
            url="https://github.com/test-user/test-repo",
            stars=100,
            created_at=datetime(2023, 1, 1),
            primary_language="Python",
            fork_count=5,
        )

        assert repo.id == 123
        assert repo.name == "test-repo"
        assert repo.owner == "test-user"
        assert repo.stars == 100
        assert repo.name_with_owner == "test-user/test-repo"
        assert repo.primary_language == "Python"
        assert repo.fork_count == 5

    def test_repository_immutability(self):
        """Test that Repository objects are immutable."""
        repo = Repository(
            id=123,
            name="test-repo",
            owner="test-user",
            url="https://github.com/test-user/test-repo",
            stars=100,
        )

        with pytest.raises(AttributeError):
            repo.stars = 200


class TestRepositoryStats:
    """Test RepositoryStats calculations."""

    def test_repository_stats_creation(self):
        """Test RepositoryStats creation with valid data."""
        stats = RepositoryStats(
            repo_id=123, stars=100, fetched_date=datetime(2023, 1, 1)
        )

        assert stats.repo_id == 123
        assert stats.stars == 100
        assert stats.fetched_date == datetime(2023, 1, 1)


class TestSearchQuery:
    """Test SearchQuery domain model."""

    def test_search_query_creation(self):
        """Test SearchQuery creation."""
        query = SearchQuery(
            query_string="language:python stars:>100",
            description="Python repositories with 100+ stars",
        )

        assert query.query_string == "language:python stars:>100"
        assert query.description == "Python repositories with 100+ stars"


class TestCrawlResult:
    """Test CrawlResult domain model."""

    def test_crawl_result_creation(self):
        """Test CrawlResult creation."""
        repos = [
            Repository(
                id=1,
                name="repo1",
                owner="user1",
                url="https://github.com/user1/repo1",
                stars=50,
            )
        ]

        result = CrawlResult(
            repositories=repos,
            total_found=1,
            query_used="language:python",
            duration_seconds=5.0,
        )

        assert len(result.repositories) == 1
        assert result.total_found == 1
        assert result.query_used == "language:python"
        assert result.duration_seconds == 5.0
        assert result.unique_owners == 1
        assert result.total_stars == 50
        assert result.average_stars == 50.0


class TestAntiCorruptionLayer:
    """Test anti-corruption layer functions."""

    def test_transform_github_response_complete(self):
        """Test transforming a complete GitHub API response."""
        api_response = {
            "databaseId": 123456,
            "name": "awesome-repo",
            "owner": {"login": "cool-user"},
            "url": "https://github.com/cool-user/awesome-repo",
            "createdAt": "2023-01-01T00:00:00Z",
            "stargazerCount": 150,
            "forkCount": 25,
            "primaryLanguage": {"name": "Python"},
            "licenseInfo": {"name": "MIT License"},
            "pushedAt": "2023-12-01T10:00:00Z",
            "updatedAt": "2023-12-01T10:30:00Z",
        }

        repo = transform_github_response(api_response)

        assert repo.id == 123456
        assert repo.name == "awesome-repo"
        assert repo.owner == "cool-user"
        assert repo.stars == 150
        assert repo.created_at is not None

    def test_transform_github_response_minimal(self):
        """Test transforming a minimal GitHub API response."""
        api_response = {
            "databaseId": 789,
            "name": "simple-repo",
            "owner": {"login": "basic-user"},
            "url": "https://github.com/basic-user/simple-repo",
            "stargazerCount": 5,
        }

        repo = transform_github_response(api_response)

        assert repo.id == 789
        assert repo.name == "simple-repo"
        assert repo.owner == "basic-user"
        assert repo.stars == 5
        assert repo.created_at is None

    def test_create_repository_stats(self):
        """Test creating repository statistics."""
        repo = Repository(
            id=123,
            name="test-repo",
            owner="test-user",
            url="https://github.com/test-user/test-repo",
            stars=100,
        )

        fetched_date = datetime(2023, 1, 1)
        stats = create_repository_stats(repo, fetched_date)

        assert stats.repo_id == 123
        assert stats.stars == 100
        assert stats.fetched_date == fetched_date

    def test_create_repository_stats_empty(self):
        """Test creating statistics with zero stars."""
        repo = Repository(
            id=456,
            name="empty-repo",
            owner="test-user",
            url="https://github.com/test-user/empty-repo",
            stars=0,
        )

        fetched_date = datetime(2023, 1, 1)
        stats = create_repository_stats(repo, fetched_date)

        assert stats.repo_id == 456
        assert stats.stars == 0
        assert stats.fetched_date == fetched_date


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_rate_limit_error(self):
        """Test RateLimitError exception."""
        with pytest.raises(RateLimitError) as exc_info:
            raise RateLimitError("Rate limit exceeded")
        assert "Rate limit exceeded" in str(exc_info.value)

    def test_authentication_error(self):
        """Test AuthenticationError exception."""
        with pytest.raises(AuthenticationError) as exc_info:
            raise AuthenticationError("Invalid token")
        assert "Invalid token" in str(exc_info.value)

    def test_search_exhausted_error(self):
        """Test SearchExhaustedError exception."""
        with pytest.raises(SearchExhaustedError) as exc_info:
            raise SearchExhaustedError("No more results")
        assert "No more results" in str(exc_info.value)

    def test_api_error(self):
        """Test ApiError exception."""
        with pytest.raises(ApiError) as exc_info:
            raise ApiError("API request failed")
        assert "API request failed" in str(exc_info.value)
