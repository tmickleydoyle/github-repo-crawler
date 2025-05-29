"""
Domain models for the GitHub crawler.

This module provides clean domain objects that isolate the core business logic
from external API concerns, implementing an anti-corruption layer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass(frozen=True)
class Repository:
    """Immutable domain model representing a GitHub repository."""

    id: int
    name: str
    owner: str
    url: str
    stars: int
    created_at: Optional[datetime] = None
    pushed_at: Optional[str] = None
    updated_at: Optional[str] = None
    primary_language: Optional[str] = None
    fork_count: int = 0
    license_name: Optional[str] = None

    @property
    def name_with_owner(self) -> str:
        """Full repository identifier in owner/name format."""
        return f"{self.owner}/{self.name}"

    def __post_init__(self):
        """Validate repository data after initialization."""
        if self.id <= 0:
            raise ValueError("Repository ID must be positive")
        if not self.name or not self.owner:
            raise ValueError("Repository name and owner are required")
        if self.stars < 0:
            raise ValueError("Star count cannot be negative")


@dataclass(frozen=True)
class RepositoryStats:
    """Immutable domain model for repository statistics at a point in time."""

    repo_id: int
    stars: int
    fetched_date: datetime

    def __post_init__(self):
        """Validate stats data after initialization."""
        if self.repo_id <= 0:
            raise ValueError("Repository ID must be positive")
        if self.stars < 0:
            raise ValueError("Star count cannot be negative")


@dataclass(frozen=True)
class SearchQuery:
    """Immutable domain model for GitHub search queries."""

    query_string: str
    description: str
    expected_results: Optional[int] = None

    def __post_init__(self):
        """Validate search query after initialization."""
        if not self.query_string.strip():
            raise ValueError("Query string cannot be empty")


class ApiError(Exception):
    """Base exception for API-related errors."""

    pass


class RateLimitError(ApiError):
    """Exception raised when GitHub API rate limit is exceeded."""

    pass


class AuthenticationError(ApiError):
    """Exception raised when GitHub API authentication fails."""

    pass


class SearchExhaustedError(ApiError):
    """Exception raised when search space is exhausted."""

    pass


@dataclass(frozen=True)
class CrawlResult:
    """Immutable result of a crawling operation."""

    repositories: List[Repository] = field(default_factory=list)
    total_found: int = 0
    query_used: Optional[str] = None
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of the crawl operation."""
        if self.total_found == 0:
            return 0.0
        return len(self.repositories) / self.total_found

    @property
    def unique_owners(self) -> int:
        """Count unique repository owners."""
        return len(set(repo.owner for repo in self.repositories))

    @property
    def total_stars(self) -> int:
        """Sum of all stars across repositories."""
        return sum(repo.stars for repo in self.repositories)

    @property
    def average_stars(self) -> float:
        """Average stars per repository."""
        if not self.repositories:
            return 0.0
        return self.total_stars / len(self.repositories)


def transform_github_response(api_response: Dict[str, Any]) -> Repository:
    """
    Transform GitHub API response into domain Repository object.

    This function implements the anti-corruption layer by converting
    external API format into our internal domain model.
    """
    try:
        repo_data = api_response

        # Parse creation date safely
        created_at = None
        if repo_data.get("createdAt"):
            # GitHub returns ISO format with Z suffix
            created_at_str = repo_data["createdAt"].replace("Z", "+00:00")
            created_at = datetime.fromisoformat(created_at_str).replace(tzinfo=None)

        return Repository(
            id=repo_data["databaseId"],
            name=repo_data["name"],
            owner=repo_data["owner"]["login"],
            url=repo_data["url"],
            stars=repo_data["stargazerCount"],
            created_at=created_at,
        )
    except (KeyError, ValueError, TypeError) as e:
        raise ValueError(f"Invalid GitHub API response format: {e}") from e


def create_repository_stats(
    repo: Repository, fetched_date: datetime
) -> RepositoryStats:
    """Create repository statistics from a repository and fetch date."""
    return RepositoryStats(repo_id=repo.id, stars=repo.stars, fetched_date=fetched_date)
