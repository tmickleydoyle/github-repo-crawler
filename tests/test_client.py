"""
Unit tests for GitHub client implementation.

These tests verify that:
1. GitHubClient initializes properly
2. Connection testing works correctly
3. Request retry mechanisms function as expected
4. GraphQL requests are handled properly
5. Rate limiting is respected
"""

import pytest
import aiohttp
from unittest.mock import AsyncMock, Mock, patch
from crawler.client import GitHubClient
from crawler.domain import (
    SearchQuery,
    RateLimitError,
    AuthenticationError,
    ApiError,
)


class TestGitHubClientInitialization:
    """Test GitHubClient initialization and setup."""

    def test_client_initialization_with_token(self):
        """Test client initializes with valid token."""
        client = GitHubClient(token="valid_token_123")

        assert client.headers["Authorization"] == "Bearer valid_token_123"
        assert client.headers["Accept"] == "application/vnd.github.v4+json"
        assert client.headers["User-Agent"] == "GitHub-Crawler/1.0"

    def test_client_initialization_invalid_token(self):
        """Test client raises error with invalid token."""
        with pytest.raises(ValueError, match="GitHub token is required"):
            GitHubClient(token="")

        with pytest.raises(ValueError, match="GitHub token is required"):
            GitHubClient(token="dummy_token_for_validation")

    def test_client_has_search_strategy(self):
        """Test client has search strategy."""
        client = GitHubClient(token="valid_token_123")
        assert hasattr(client, "search_strategy")
        assert client.search_strategy is not None

    def test_client_has_connector(self):
        """Test client can create connection pool."""
        client = GitHubClient(token="valid_token_123")
        assert client._connector is None


class TestGitHubClientContextManager:
    """Test GitHubClient async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_session_creation(self):
        """Test context manager creates session."""
        client = GitHubClient(token="valid_token_123")

        async with client as c:
            assert hasattr(c, "_session")
            assert isinstance(c._session, aiohttp.ClientSession)

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """Test context manager cleans up resources."""
        client = GitHubClient(token="valid_token_123")

        with patch.object(
            aiohttp.ClientSession, "close", new_callable=AsyncMock
        ) as mock_session_close, patch.object(
            aiohttp.TCPConnector, "close", new_callable=AsyncMock
        ) as mock_connector_close:

            async with client:
                pass

            mock_session_close.assert_called_once()
            mock_connector_close.assert_called_once()


class TestGitHubClientConnection:
    """Test GitHub API connection functionality."""

    @pytest.mark.asyncio
    async def test_connection_test_success(self):
        """Test successful connection test."""
        client = GitHubClient(token="valid_token_123")

        mock_response = {
            "data": {
                "viewer": {"login": "test_user"},
                "rateLimit": {
                    "remaining": 5000,
                    "resetAt": "2025-01-01T00:00:00Z",
                },
            }
        }

        with patch.object(
            client, "_make_graphql_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            async with client:
                result = await client.test_connection()

                assert result is True
                mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_test_failure(self):
        """Test connection test failure."""
        client = GitHubClient(token="valid_token_123")

        with patch.object(
            client, "_make_graphql_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = AuthenticationError("Invalid token")

            async with client:
                result = await client.test_connection()

                assert result is False


class TestGitHubClientRequestHandling:
    """Test GitHub API request handling and retry logic."""

    @pytest.mark.asyncio
    async def test_graphql_request_success(self):
        """Test successful GraphQL request."""
        client = GitHubClient(token="valid_token_123")

        mock_response_data = {
            "data": {"search": {"nodes": []}},
        }

        async with client:
            with patch.object(client._session, "post") as mock_post:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value=mock_response_data)
                mock_response.headers = {"X-RateLimit-Remaining": "1000"}

                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_response)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                mock_post.return_value = mock_context

                result = await client._make_graphql_request({"query": "test"})

                assert result == mock_response_data

    @pytest.mark.asyncio
    async def test_graphql_request_rate_limit(self):
        """Test GraphQL request handles rate limiting."""
        client = GitHubClient(token="valid_token_123")

        async with client:
            with patch.object(client._session, "post") as mock_post, patch(
                "asyncio.sleep", new_callable=AsyncMock
            ):
                mock_response = AsyncMock()
                mock_response.status = 403
                mock_response.text = AsyncMock(return_value="rate limit exceeded")

                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_response)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                mock_post.return_value = mock_context

                with pytest.raises(RateLimitError):
                    await client._make_graphql_request({"query": "test"})

    @pytest.mark.asyncio
    async def test_graphql_request_authentication_error(self):
        """Test GraphQL request handles authentication errors."""
        client = GitHubClient(token="valid_token_123")

        mock_response = AsyncMock()
        mock_response.status = 401

        with patch.object(client, "_session") as mock_session:
            mock_session.post.return_value.__aenter__.return_value = mock_response

            async with client:
                with pytest.raises(AuthenticationError):
                    await client._make_graphql_request({"query": "test"})

    @pytest.mark.asyncio
    async def test_graphql_request_server_error(self):
        """Test GraphQL request handles server errors with retry."""
        client = GitHubClient(token="valid_token_123")

        async with client:
            with patch.object(client._session, "post") as mock_post:
                mock_response = AsyncMock()
                mock_response.status = 502
                mock_response.request_info = Mock()
                mock_response.history = Mock()

                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_response)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                mock_post.return_value = mock_context

                with pytest.raises(aiohttp.ClientResponseError):
                    await client._make_graphql_request({"query": "test"})


class TestGitHubClientSearchRepositories:
    """Test repository search functionality."""

    @pytest.mark.asyncio
    async def test_search_repositories_success(self):
        """Test successful repository search."""
        client = GitHubClient(token="valid_token_123")

        search_query = SearchQuery(
            query_string="language:python stars:>100",
            description="Python repositories with 100+ stars",
        )

        mock_api_response = {
            "data": {
                "search": {
                    "nodes": [
                        {
                            "databaseId": 123,
                            "name": "test-repo",
                            "owner": {"login": "test-user"},
                            "url": "https://github.com/test-user/test-repo",
                            "stargazerCount": 150,
                            "createdAt": "2023-01-01T00:00:00Z",
                            "forkCount": 25,
                            "primaryLanguage": {"name": "Python"},
                            "licenseInfo": {"name": "MIT"},
                            "pushedAt": "2023-12-01T00:00:00Z",
                            "updatedAt": "2023-12-01T00:00:00Z",
                        }
                    ],
                    "pageInfo": {"endCursor": "abc123", "hasNextPage": True},
                    "repositoryCount": 1,
                },
                "rateLimit": {
                    "remaining": 4999,
                    "resetAt": "2025-01-01T00:00:00Z",
                },
            }
        }

        with patch.object(
            client, "_make_graphql_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_api_response

            async with client:
                result = await client.search_repositories(search_query)

                assert "repositories" in result
                assert len(result["repositories"]) == 1

                repo = result["repositories"][0]
                assert repo.name == "test-repo"
                assert repo.owner == "test-user"
                assert repo.stars == 150

                assert result["pageInfo"]["hasNextPage"] is True
                assert result["repositoryCount"] == 1

    @pytest.mark.asyncio
    async def test_search_repositories_with_pagination(self):
        """Test repository search with pagination cursor."""
        client = GitHubClient(token="valid_token_123")

        search_query = SearchQuery(
            query_string="test query", description="Test query for pagination"
        )

        with patch.object(
            client, "_make_graphql_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {
                "data": {
                    "search": {
                        "nodes": [],
                        "pageInfo": {"endCursor": None, "hasNextPage": False},
                        "repositoryCount": 0,
                    },
                    "rateLimit": {"remaining": 5000},
                }
            }

            async with client:
                await client.search_repositories(search_query, after="cursor123")

                call_args = mock_request.call_args[0][0]
                assert call_args["variables"]["after"] == "cursor123"

    @pytest.mark.asyncio
    async def test_search_repositories_api_error(self):
        """Test repository search handles API errors."""
        client = GitHubClient(token="valid_token_123")

        search_query = SearchQuery(
            query_string="test query",
            description="Test query for API error handling",
        )

        with patch.object(
            client, "_make_graphql_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = ApiError("API failed")

            async with client:
                with pytest.raises(ApiError):
                    await client.search_repositories(search_query)


class TestGitHubClientCrawl:
    """Test main crawl functionality."""

    @pytest.mark.asyncio
    async def test_crawl_basic_functionality(self):
        """Test basic crawl functionality."""
        client = GitHubClient(token="valid_token_123")

        mock_queries = [
            SearchQuery(query_string="test query 1", description="Test query 1"),
            SearchQuery(query_string="test query 2", description="Test query 2"),
        ]

        with patch.object(client.search_strategy, "generate_queries") as mock_generate:
            mock_generate.return_value = mock_queries

            with patch.object(
                client, "_crawl_query", new_callable=AsyncMock
            ) as mock_crawl_query:
                async with client:
                    result = await client.crawl(matrix_total=2, matrix_index=0)

                    assert hasattr(result, "repositories")
                    assert hasattr(result, "total_found")
                    assert hasattr(result, "unique_owners")
                    assert hasattr(result, "total_stars")
                    assert isinstance(result.repositories, list)

                    mock_generate.assert_called_once_with(0, 2)

                    assert mock_crawl_query.call_count == len(mock_queries)
