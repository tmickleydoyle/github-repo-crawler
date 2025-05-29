import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    github_token: str
    github_api_url: str = "https://api.github.com/graphql"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/crawler"
    batch_size: int = 100  # GitHub GraphQL API max is 100 per request
    max_repos: int = int(os.getenv('MAX_REPOS', '1000'))  # Read from environment, default 1000
    total_matrix_jobs: int = 100  # 100 matrix jobs for 100,000 total repos
    total_target_repos: int = 100000  # Total repositories across all matrix jobs

    class Config:
        env_file = ".env"

settings = Settings()
