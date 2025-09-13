"""
Data models for the GitHub crawler application.

These Pydantic models define the structure of data collected from GitHub
and stored in the database. They provide validation, serialization, and
type safety for the crawler operations.
"""

from datetime import date, datetime
from typing import List, Optional

from dateutil import parser as date_parser
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Repo(BaseModel):
    """
    Represents a GitHub repository with comprehensive metadata.

    This model stores enhanced information about a repository
    that is collected from the GitHub API and stored in the database.
    """

    # Core identity fields
    id: int
    name: str
    owner: str
    url: str
    created_at: datetime
    alphabet_partition: Optional[str] = None

    # Repository content and description
    description: Optional[str] = None
    homepage_url: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)

    # Repository statistics
    watchers_count: int = 0
    open_issues_count: int = 0
    subscribers_count: int = 0
    network_count: int = 0
    size_kb: int = 0

    # Repository configuration
    default_branch: str = "main"
    visibility: str = "public"
    license_name: Optional[str] = None
    primary_language: Optional[str] = None

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

    # Timestamp fields
    pushed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("created_at", "pushed_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        """
        Parse datetime strings from GitHub API into Python datetime objects.

        Handles various datetime formats and ensures timezone-naive datetimes
        for consistent database storage.
        """
        if v is None:
            return v
        if isinstance(v, str):
            dt = date_parser.parse(v)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        return v


class RepoStats(BaseModel):
    """
    Represents repository statistics at a point in time.

    This model stores metrics like star counts that change over time,
    allowing for historical tracking and trend analysis.
    """

    repo_id: int = Field(..., alias="repoId")
    fetched_date: date
    stars: int

    model_config = ConfigDict(populate_by_name=True)
