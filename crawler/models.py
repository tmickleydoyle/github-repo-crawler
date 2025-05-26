from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from dateutil import parser as date_parser
from typing import Optional

class Repo(BaseModel):
    id: int
    name: str
    owner: str
    url: str
    created_at: datetime
    alphabet_partition: Optional[str] = None  # Track which alphabet partition crawled this repo
    
    @field_validator('created_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            # Parse the ISO string and convert to naive datetime (UTC)
            dt = date_parser.parse(v)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        return v

class RepoStats(BaseModel):
    repo_id: int = Field(..., alias="repoId")
    fetched_date: date
    stars: int

class RepoArchive(BaseModel):
    repo_id: int
    fetched_date: date
    archive_path: str

class RepoFileIndex(BaseModel):
    repo_id: int
    fetched_date: date
    path: str
    content_sha: str
