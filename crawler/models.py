"""
Data models for the GitHub crawler application.

These Pydantic models define the structure of data collected from GitHub
and stored in the database. They provide validation, serialization, and
type safety for the crawler operations.
"""

from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from dateutil import parser as date_parser
from typing import Optional

class Repo(BaseModel):
    """
    Represents a GitHub repository with core metadata.
    
    This model stores the essential information about a repository
    that is collected from the GitHub API and stored in the database.
    """
    id: int                                    # GitHub's unique repository ID
    name: str                                  # Repository name (e.g., "react")
    owner: str                                 # Owner/organization name (e.g., "facebook")
    url: str                                   # Full GitHub URL
    created_at: datetime                       # When the repo was created on GitHub
    alphabet_partition: Optional[str] = None   # Crawling partition identifier
    
    @field_validator('created_at', mode='before')
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
    repo_id: int = Field(..., alias="repoId")  # Foreign key to repo table
    fetched_date: date                         # Date when stats were collected
    stars: int                                 # Number of stars at this date
    
    class Config:
        """Pydantic configuration for the model."""
        populate_by_name = True  # Allow both 'repo_id' and 'repoId' field names
