# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a high-performance GitHub repository crawler using GraphQL API designed for scalability and production use.

## Commands

**Development:**
- `make install-dev` - Install all dependencies including development tools
- `make run` - Run the crawler locally (100 repos, single job)
- `make format` - Format code with ruff
- `make lint` - Lint code with ruff
- `make type-check` - Type check with mypy (strict mode)
- `make quality` - Run all quality checks (lint, type, test)

**Testing:**
- `make test` - Run all tests
- `make test-unit` - Run unit tests only
- `make test-integration` - Run integration tests only
- `make test-coverage` - Run tests with coverage report

**Database:**
- `make db-migrate` - Create new database migration
- `make db-upgrade` - Apply database migrations
- `make db-downgrade` - Rollback database migrations

**Docker:**
- `make docker-build` - Build production Docker image
- `make docker-build-dev` - Build development Docker image
- `make docker-run` - Run with docker-compose

## Architecture

**Core Modules:**
- `crawler/config.py` - Centralized configuration using Pydantic Settings
- `crawler/main.py` - Application entry point with structured logging
- `crawler/client.py` - GitHub GraphQL API client with retry logic
- `crawler/db_repository.py` - Centralized database operations (Repository pattern)
- `crawler/domain.py` - Domain models and business logic
- `crawler/logger.py` - Structured logging with structlog
- `crawler/search_strategy.py` - Search strategy implementations

**Key Patterns:**
- **Repository Pattern:** All database operations centralized in `DatabaseRepository` class
- **Dependency Injection:** Settings injected via `get_settings()` function
- **Structured Logging:** All operations logged with context using structlog
- **Async/Await:** Full async architecture for I/O operations
- **Configuration:** Flat Pydantic Settings with environment variable mapping

## Configuration

All configuration is centralized in `crawler/config.py` using a flat structure for performance:

```python
from crawler.config import get_settings
settings = get_settings()

# Database access
settings.database_host
settings.database_url  # Computed property

# GitHub API
settings.github_token
settings.github_api_url

# Crawler behavior
settings.crawler_max_repos
settings.crawler_batch_size
```

Environment variables are automatically mapped (see config.py for full list).

## Database Operations

All database operations go through the centralized `DatabaseRepository`:

```python
from crawler.db_repository import DatabaseRepository

async with DatabaseRepository() as db_repo:
    await db_repo.initialize_schema()
    stats = await db_repo.store_repositories(crawl_result, matrix_index)
```

This ensures:
- Connection pooling and proper resource management
- Consistent error handling and logging
- Transaction safety
- Easy testing and mocking

## Logging

Use structured logging throughout:

```python
from crawler.logger import get_logger, LogContext

logger = get_logger(__name__, component="crawler")
logger.info("Operation started", repos_count=100, matrix_index=0)

# For operations with timing
async with LogContext(logger, "database_operation", **context):
    # Operation code here
    pass
```

## Testing

- Tests are in `tests/` directory
- Use `@pytest.mark.integration` for integration tests
- Mock external dependencies (GitHub API, database)
- Use `pytest-asyncio` for async tests

## GitHub Actions

The workflow supports:
- Modern Python packaging with pyproject.toml
- Code quality checks with ruff and mypy
- Matrix-based parallel crawling
- Automatic database exports
- Proper artifact handling

Run manually via Actions tab with configurable matrix size and repos per job.

## Performance Considerations

- Uses connection pooling for database operations
- Async/await throughout for I/O concurrency
- Structured logging avoids string formatting overhead
- Flat configuration structure reduces object creation
- Repository pattern centralizes and optimizes database queries
- GraphQL batch operations reduce API calls