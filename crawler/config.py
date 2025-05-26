from pydantic import HttpUrl
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    github_token: str
    github_api_url: HttpUrl = "https://api.github.com/graphql"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/crawler"
    batch_size: int = 100
    max_repos: int = 100000

    class Config:
        env_file = ".env"

settings = Settings()
