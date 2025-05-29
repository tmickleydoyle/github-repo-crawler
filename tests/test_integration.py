"""
Integration tests for GitHub crawler end-to-end functionality.

These tests verify that:
1. Complete crawl workflow works correctly
2. Database operations integrate properly
3. Error handling works in realistic scenarios
4. Performance is acceptable under load
"""

import pytest
import os
from datetime import datetime
from unittest.mock import patch, AsyncMock
from crawler.main import run, store_repositories
from crawler.domain import Repository, CrawlResult


class TestCrawlerIntegration:
    """Integration tests for complete crawler workflow."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_end_to_end_crawl_workflow(self):
        """Test complete crawl workflow from start to finish."""
        # Mock environment variables
        with patch.dict(
            os.environ,
            {
                "GITHUB_TOKEN": "test_token_123",
                "POSTGRES_HOST": "localhost",
                "POSTGRES_DB": "test_db",
            },
        ):
            # Mock GitHubClient to return test data
            mock_repositories = [
                Repository(
                    id=1,
                    name="test-repo-1",
                    owner="test-user-1",
                    url="https://github.com/test-user-1/test-repo-1",
                    stars=100,
                ),
                Repository(
                    id=2,
                    name="test-repo-2",
                    owner="test-user-2",
                    url="https://github.com/test-user-2/test-repo-2",
                    stars=50,
                ),
            ]

            mock_crawl_result = CrawlResult(
                repositories=mock_repositories,
                total_found=2,
                query_used="language:python stars:>50",
                duration_seconds=1.5,
            )

            # Mock the GitHubClient methods
            with patch("crawler.main.GitHubClient") as MockClient:
                mock_client = MockClient.return_value
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.test_connection = AsyncMock(return_value=True)
                mock_client.crawl = AsyncMock(return_value=mock_crawl_result)

                # Mock database operations
                with patch(
                    "crawler.main.store_repositories", new_callable=AsyncMock
                ) as mock_store:
                    # Mock command line arguments
                    with patch("crawler.main.parse_args") as mock_args:
                        mock_args.return_value.repos = 1000
                        mock_args.return_value.matrix_total = 1
                        mock_args.return_value.matrix_index = 0

                        # Run the main function
                        await run()

                        # Verify the workflow
                        mock_client.test_connection.assert_called_once()
                        mock_client.crawl.assert_called_once_with(
                            matrix_total=1, matrix_index=0
                        )
                        mock_store.assert_called_once_with(mock_crawl_result, 0)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_crawl_with_connection_failure(self):
        """Test crawl behavior when GitHub connection fails."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token_123"}):
            with patch("crawler.main.GitHubClient") as MockClient:
                mock_client = MockClient.return_value
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.test_connection = AsyncMock(return_value=False)

                with patch("crawler.main.parse_args") as mock_args:
                    mock_args.return_value.repos = 1000
                    mock_args.return_value.matrix_total = 1
                    mock_args.return_value.matrix_index = 0

                    # Should complete without error but not proceed to crawl
                    await run()

                    mock_client.test_connection.assert_called_once()
                    # crawl should not be called if connection fails
                    mock_client.crawl.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_integration(self):
        """Test database operations with mock database."""
        # Create test repositories
        test_repositories = [
            Repository(
                id=12345,
                name="integration-test-repo",
                owner="test-owner",
                url="https://github.com/test-owner/integration-test-repo",
                stars=75,
                created_at=datetime(2023, 1, 1),
            )
        ]

        test_crawl_result = CrawlResult(
            repositories=test_repositories,
            total_found=1,
            query_used="language:python",
            duration_seconds=0.8,
        )

        # Mock asyncpg connection
        with patch("crawler.main.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            # Mock transaction context manager properly
            mock_transaction = AsyncMock()
            mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
            mock_transaction.__aexit__ = AsyncMock(return_value=None)

            # Make transaction() return the mock transaction directly, not a coroutine
            mock_conn.transaction = lambda: mock_transaction

            await store_repositories(test_crawl_result, matrix_index=0)

            # Verify database operations were called
            mock_connect.assert_called_once()
            # Should be called multiple times for table creation and inserts
            mock_conn.execute.assert_called()
            mock_conn.close.assert_called_once()


class TestErrorHandling:
    """Integration tests for error handling scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_client_initialization_error(self):
        """Test handling of client initialization errors."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": ""}):
            with patch("crawler.main.GitHubClient") as MockClient:
                MockClient.side_effect = ValueError("GitHub token is required")

                with patch("crawler.main.parse_args") as mock_args:
                    mock_args.return_value.repos = 1000
                    mock_args.return_value.matrix_total = 1
                    mock_args.return_value.matrix_index = 0

                    # Should raise the ValueError
                    with pytest.raises(ValueError):
                        await run()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_connection_error(self):
        """Test handling of database connection errors."""
        test_crawl_result = CrawlResult(
            repositories=[],
            total_found=0,
            query_used="test:query",
            duration_seconds=0.0,
        )

        # Mock database connection failure
        with patch("crawler.main.asyncpg.connect") as mock_connect:
            mock_connect.side_effect = Exception("Database connection failed")

            # Should raise the database error
            with pytest.raises(Exception, match="Database connection failed"):
                await store_repositories(test_crawl_result, matrix_index=0)


class TestPerformance:
    """Integration tests for performance characteristics."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_large_repository_set_handling(self):
        """Test handling of large repository sets."""
        # Create a large set of mock repositories
        large_repo_set = []
        for i in range(1, 1001):  # Start from 1 instead of 0
            repo = Repository(
                id=i,
                name=f"repo-{i}",
                owner=f"user-{i % 100}",  # 100 unique owners
                url=f"https://github.com/user-{i % 100}/repo-{i}",
                stars=i % 1000,
            )
            large_repo_set.append(repo)

        large_crawl_result = CrawlResult(
            repositories=large_repo_set,
            total_found=1000,
            query_used="large test query",
            duration_seconds=5.0,
        )

        # Mock database operations
        with patch("crawler.main.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            # Mock transaction context manager properly
            mock_transaction = AsyncMock()
            mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
            mock_transaction.__aexit__ = AsyncMock(return_value=None)

            # Make transaction() return the mock transaction directly, not a coroutine
            mock_conn.transaction = lambda: mock_transaction

            # Time the operation
            import time

            start_time = time.time()

            await store_repositories(large_crawl_result, matrix_index=0)

            end_time = time.time()
            duration = end_time - start_time

            # Should complete in reasonable time (< 5 seconds for mock operations)
            assert duration < 5.0

            # Verify all repositories were processed
            # execute should be called for each repo (insert into repo + repo_stats)
            # + table creation
            # 2 inserts per repo + 7 for table/index creation
            expected_calls = len(large_repo_set) * 2 + 7
            assert mock_conn.execute.call_count >= expected_calls
