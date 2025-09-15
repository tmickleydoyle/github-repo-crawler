"""Configuration management using Pydantic Settings."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
        env_prefix="",
    )

    # Environment and debug
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")

    # Database settings
    database_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    database_port: int = Field(default=5432, alias="POSTGRES_PORT")
    database_name: str = Field(default="crawler", alias="POSTGRES_DB")
    database_username: str = Field(default="postgres", alias="POSTGRES_USER")
    database_password: SecretStr = Field(
        default=SecretStr("postgres"), alias="POSTGRES_PASSWORD"
    )
    database_pool_size: int = Field(default=20, alias="DB_POOL_SIZE")
    database_max_overflow: int = Field(default=40, alias="DB_MAX_OVERFLOW")

    # GitHub settings
    github_token: SecretStr = Field(default=SecretStr(""), alias="GITHUB_TOKEN")
    github_api_url: str = Field(
        default="https://api.github.com/graphql", alias="GITHUB_API_URL"
    )
    github_rate_limit_threshold: int = Field(
        default=100, alias="GITHUB_RATE_LIMIT_THRESHOLD"
    )
    github_retry_max_attempts: int = Field(default=5, alias="GITHUB_RETRY_MAX_ATTEMPTS")
    github_retry_backoff_factor: float = Field(
        default=2.0, alias="GITHUB_RETRY_BACKOFF_FACTOR"
    )

    # Crawler settings - optimized for performance
    crawler_batch_size: int = Field(
        default=500, alias="BATCH_SIZE"
    )  # Increased for better batching
    crawler_max_repos: int = Field(default=4000, alias="MAX_REPOS")
    crawler_total_matrix_jobs: int = Field(default=200, alias="TOTAL_MATRIX_JOBS")
    crawler_total_target_repos: int = Field(default=800000, alias="TOTAL_TARGET_REPOS")
    crawler_concurrent_requests: int = Field(
        default=15, alias="CONCURRENT_REQUESTS"
    )  # Higher for better throughput
    crawler_request_timeout: int = Field(default=30, alias="REQUEST_TIMEOUT")

    # Logging settings
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    log_enable_colors: bool = Field(default=True, alias="LOG_COLORS")
    log_include_timestamp: bool = Field(default=True, alias="LOG_TIMESTAMP")

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        allowed = ["development", "staging", "production", "testing"]
        if v.lower() not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v.lower()

    @property
    def database_url(self) -> str:
        """Generate database URL from components."""
        pwd = self.database_password.get_secret_value()
        return f"postgresql://{self.database_username}:{pwd}@{self.database_host}:{self.database_port}/{self.database_name}"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# For module-level access
settings = get_settings()
