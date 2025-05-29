"""
pytest configuration for GitHub crawler tests.

This file configures:
1. Async test support
2. Test markers for different test types
3. Fixtures for common test data
4. Mock configurations
"""

import pytest
import asyncio
from unittest.mock import Mock


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_github_api_response():
    """Fixture providing a mock GitHub API response."""
    return {
        "data": {
            "search": {
                "nodes": [
                    {
                        "databaseId": 123456,
                        "name": "test-repo",
                        "owner": {"login": "test-user"},
                        "url": "https://github.com/test-user/test-repo",
                        "createdAt": "2023-01-01T00:00:00Z",
                        "stargazerCount": 100,
                        "forkCount": 10,
                        "primaryLanguage": {"name": "Python"},
                        "licenseInfo": {"name": "MIT License"},
                        "pushedAt": "2023-12-01T10:00:00Z",
                        "updatedAt": "2023-12-01T10:30:00Z",
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


@pytest.fixture
def mock_repository_list():
    """Fixture providing a list of mock repositories."""
    from crawler.domain import Repository

    return [
        Repository(
            id=1,
            name="repo1",
            owner="user1",
            url="https://github.com/user1/repo1",
            name_with_owner="user1/repo1",
            stargazer_count=100,
            primary_language="Python",
        ),
        Repository(
            id=2,
            name="repo2",
            owner="user2",
            url="https://github.com/user2/repo2",
            name_with_owner="user2/repo2",
            stargazer_count=50,
            primary_language="JavaScript",
        ),
        Repository(
            id=3,
            name="repo3",
            owner="user1",
            url="https://github.com/user1/repo3",
            name_with_owner="user1/repo3",
            stargazer_count=200,
            primary_language="Python",
        ),
    ]


@pytest.fixture
def github_client_token():
    """Fixture providing a test GitHub token."""
    return "test_token_12345"


@pytest.fixture
def mock_aiohttp_session():
    """Fixture providing a mock aiohttp session."""
    session = Mock()
    session.post = Mock()
    session.close = Mock()
    return session
