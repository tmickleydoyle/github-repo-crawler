"""
Domain models for the GitHub crawler.

This module provides clean domain objects that isolate the core business logic
from external API concerns, implementing an anti-corruption layer.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Repository:
    """Immutable domain model representing a GitHub repository with
    comprehensive metadata."""

    # Core identity fields
    id: int
    name: str
    owner: str
    url: str
    stars: int

    # Basic metadata
    created_at: Optional[datetime] = None
    pushed_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Language and technology
    primary_language: Optional[str] = None
    languages: List[str] = field(default_factory=list)

    # Repository statistics
    fork_count: int = 0
    watchers_count: int = 0
    open_issues_count: int = 0

    # Repository content and features
    description: Optional[str] = None
    homepage_url: Optional[str] = None
    topics: List[str] = field(default_factory=list)

    # Repository settings
    license_name: Optional[str] = None
    default_branch: str = "main"
    visibility: str = "public"

    # Repository state flags
    is_fork: bool = False
    is_archived: bool = False
    is_disabled: bool = False
    is_template: bool = False
    has_issues: bool = True
    has_projects: bool = True
    has_wiki: bool = True
    has_pages: bool = False
    has_downloads: bool = True

    # Additional metrics
    size_kb: int = 0
    network_count: int = 0  # Total forks across the network
    subscribers_count: int = 0

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
    external API format into our internal domain model with comprehensive
    metadata extraction.
    """
    try:
        repo_data = api_response

        # Parse datetime fields
        created_at = None
        if repo_data.get("createdAt"):
            created_at_str = repo_data["createdAt"].replace("Z", "+00:00")
            created_at = datetime.fromisoformat(created_at_str).replace(tzinfo=None)

        # Extract languages list
        languages = []
        if repo_data.get("languages", {}).get("nodes"):
            languages = [lang["name"] for lang in repo_data["languages"]["nodes"]]

        # Extract topics list
        topics = []
        if repo_data.get("repositoryTopics", {}).get("nodes"):
            topics = [
                topic["topic"]["name"]
                for topic in repo_data["repositoryTopics"]["nodes"]
            ]

        # Extract license name
        license_name = None
        if repo_data.get("licenseInfo") and repo_data["licenseInfo"].get("name"):
            license_name = repo_data["licenseInfo"]["name"]

        # Extract primary language
        primary_language = None
        if repo_data.get("primaryLanguage") and repo_data["primaryLanguage"].get(
            "name"
        ):
            primary_language = repo_data["primaryLanguage"]["name"]

        # Extract default branch
        default_branch = "main"
        if repo_data.get("defaultBranchRef") and repo_data["defaultBranchRef"].get(
            "name"
        ):
            default_branch = repo_data["defaultBranchRef"]["name"]

        return Repository(
            # Core identity
            id=repo_data["databaseId"],
            name=repo_data["name"],
            owner=repo_data["owner"]["login"],
            url=repo_data["url"],
            stars=repo_data["stargazerCount"],
            # Basic metadata
            created_at=created_at,
            pushed_at=repo_data.get("pushedAt"),
            updated_at=repo_data.get("updatedAt"),
            # Language and technology
            primary_language=primary_language,
            languages=languages,
            # Repository statistics
            fork_count=repo_data.get("forkCount", 0),
            watchers_count=repo_data.get("watchers", {}).get("totalCount", 0),
            open_issues_count=repo_data.get("issues", {}).get("totalCount", 0),
            # Repository content and features
            description=repo_data.get("description"),
            homepage_url=repo_data.get("homepageUrl"),
            topics=topics,
            # Repository settings
            license_name=license_name,
            default_branch=default_branch,
            visibility=repo_data.get("visibility", "public").lower(),
            # Repository state flags
            is_fork=repo_data.get("isFork", False),
            is_archived=repo_data.get("isArchived", False),
            is_disabled=repo_data.get("isDisabled", False),
            is_template=repo_data.get("isTemplate", False),
            has_issues=repo_data.get("hasIssuesEnabled", True),
            has_projects=repo_data.get("hasProjectsEnabled", True),
            has_wiki=repo_data.get("hasWikiEnabled", True),
            has_pages=repo_data.get("hasPages", False),
            has_downloads=repo_data.get("hasDownloads", True),
            # Additional metrics
            size_kb=repo_data.get("diskUsage", 0),
            network_count=repo_data.get("networkCount", {}).get("totalCount", 0),
            subscribers_count=repo_data.get("subscribers", {}).get("totalCount", 0),
        )
    except (KeyError, ValueError, TypeError) as e:
        raise ValueError(f"Invalid GitHub API response format: {e}") from e


def create_repository_stats(
    repo: Repository, fetched_date: datetime
) -> RepositoryStats:
    """Create repository statistics from a repository and fetch date."""
    return RepositoryStats(repo_id=repo.id, stars=repo.stars, fetched_date=fetched_date)


def repository_to_repo_model(
    repository: Repository, alphabet_partition: Optional[str] = None
):
    """Convert domain Repository to models.Repo for database operations."""
    from .models import Repo

    # Parse timestamp fields
    pushed_at = None
    if repository.pushed_at:
        try:
            if isinstance(repository.pushed_at, str):
                pushed_at_str = repository.pushed_at.replace("Z", "+00:00")
                pushed_at = datetime.fromisoformat(pushed_at_str).replace(tzinfo=None)
            elif isinstance(repository.pushed_at, datetime):
                pushed_at = (
                    repository.pushed_at.replace(tzinfo=None)
                    if repository.pushed_at.tzinfo
                    else repository.pushed_at
                )
        except (ValueError, TypeError):
            pushed_at = None

    updated_at = None
    if repository.updated_at:
        try:
            if isinstance(repository.updated_at, str):
                updated_at_str = repository.updated_at.replace("Z", "+00:00")
                updated_at = datetime.fromisoformat(updated_at_str).replace(tzinfo=None)
            elif isinstance(repository.updated_at, datetime):
                updated_at = (
                    repository.updated_at.replace(tzinfo=None)
                    if repository.updated_at.tzinfo
                    else repository.updated_at
                )
        except (ValueError, TypeError):
            updated_at = None

    return Repo(
        # Core identity
        id=repository.id,
        name=repository.name,
        owner=repository.owner,
        url=repository.url,
        created_at=repository.created_at or datetime.now(),
        alphabet_partition=alphabet_partition,
        # Repository content and description
        description=repository.description,
        homepage_url=repository.homepage_url,
        topics=repository.topics,
        languages=repository.languages,
        # Repository statistics
        watchers_count=repository.watchers_count,
        open_issues_count=repository.open_issues_count,
        subscribers_count=repository.subscribers_count,
        network_count=repository.network_count,
        size_kb=repository.size_kb,
        # Repository configuration
        default_branch=repository.default_branch,
        visibility=repository.visibility,
        license_name=repository.license_name,
        primary_language=repository.primary_language,
        # Repository state flags
        is_fork=repository.is_fork,
        is_archived=repository.is_archived,
        is_disabled=repository.is_disabled,
        is_template=repository.is_template,
        has_issues=repository.has_issues,
        has_projects=repository.has_projects,
        has_wiki=repository.has_wiki,
        has_pages=repository.has_pages,
        has_downloads=repository.has_downloads,
        # Timestamp fields
        pushed_at=pushed_at,
        updated_at=updated_at,
    )


def repository_to_repo_stats_model(repository: Repository, fetched_date: date):
    """Convert domain Repository to models.RepoStats for database operations."""
    from .models import RepoStats

    return RepoStats(
        repo_id=repository.id,
        fetched_date=fetched_date,
        stars=repository.stars,
    )
