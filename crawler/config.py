import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    github_token: str = os.getenv("GITHUB_TOKEN", "dummy_token_for_validation")
    github_api_url: str = "https://api.github.com/graphql"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/crawler"
    batch_size: int = 100
    max_repos: int = int(os.getenv("MAX_REPOS", "4000"))  # Ultra-aggressive: 4K per job  
    total_matrix_jobs: int = 200  # 200 parallel jobs
    total_target_repos: int = 800000  # Target 800K repos total (4K × 200 jobs)


settings = Settings()
