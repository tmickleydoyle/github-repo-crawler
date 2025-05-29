"""
Data models for the GitHub crawler application.

These Pydantic models define the structure of data collected from GitHub
and stored in the database. They provide validation, serialization, and
type safety for the crawler operations.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import date, datetime
from dateutil import parser as date_parser
from typing import Optional


class Repo(BaseModel):
    """
    Represents a GitHub repository with core metadata.

    This model stores the essential information about a repository
    that is collected from the GitHub API and stored in the database.
    """

    id: int
    name: str
    owner: str
    url: str
    created_at: datetime
    alphabet_partition: Optional[str] = None

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        """
        Parse datetime strings from GitHub API into Python datetime objects.

        Handles various datetime formats and ensures timezone-naive datetimes
        for consistent database storage.
        """
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
