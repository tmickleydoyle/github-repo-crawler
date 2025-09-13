import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized configuration management for the GitHub crawler."""
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # GitHub API Configuration
    github_token: str = "dummy_token_for_validation"
    github_api_url: str = "https://api.github.com/graphql"
    
    # Database Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "crawler"
    
    # Crawler Configuration
    batch_size: int = 100
    max_repos: int = 4000
    total_matrix_jobs: int = 200
    total_target_repos: int = 800000
    
    # Connection Configuration
    max_connections: int = 100
    max_connections_per_host: int = 20
    connection_timeout: int = 30
    request_timeout: int = 30
    
    @property
    def database_url(self) -> str:
        """Construct database URL from individual components."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
