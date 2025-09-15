## Project Structure & Organization

**Use a standard project layout** with clear separation of concerns. Organize code into logical modules with `src/` or package-name directories, separate `tests/`, `docs/`, and configuration files at the root level.

**Implement proper package management** using `pyproject.toml` for modern Python projects, with tools like Poetry or pip-tools for dependency management. Pin exact versions in production and use virtual environments consistently.

## Code Quality & Standards

**Follow PEP 8 and use automated formatting** with Black, isort for imports, and flake8 or ruff for linting. Configure these tools in your project to maintain consistent code style across the team.

**Write comprehensive tests** using pytest with good coverage (aim for 80%+). Include unit tests, integration tests, and end-to-end tests. Use fixtures, parameterized tests, and mock external dependencies appropriately.

**Implement proper error handling** with specific exception types, logging at appropriate levels, and graceful degradation. Use structured logging with libraries like structlog for better observability.

## Architecture & Design

**Design for modularity and maintainability** using dependency injection, clear interfaces, and the principle of least privilege. Consider using design patterns like Repository, Factory, or Strategy where appropriate.

**Separate configuration from code** using environment variables, configuration files, or tools like Pydantic Settings. Never hardcode secrets or environment-specific values.

**Implement proper database patterns** with connection pooling, migrations (using Alembic), and ORM best practices if using SQLAlchemy. Consider async patterns for I/O-bound operations.

## Security & Performance

**Validate all inputs** using libraries like Pydantic for data validation and serialization. Sanitize user inputs and implement proper authentication and authorization.

**Optimize for performance** by profiling bottlenecks, using appropriate data structures, implementing caching strategies, and considering async/await for concurrent operations.

**Handle secrets securely** using environment variables, secret management services, or tools like python-dotenv for development. Never commit secrets to version control.

## Development Workflow

**Use version control effectively** with meaningful commit messages, feature branches, and code review processes. Implement pre-commit hooks for automated checks.

**Set up CI/CD pipelines** that run tests, linting, security scans, and automated deployments. Use tools like GitHub Actions, GitLab CI, or Jenkins.

**Implement proper logging and monitoring** with structured logs, metrics collection, and alerting. Use tools like Prometheus, Grafana, or application performance monitoring solutions.

## Documentation & Deployment

**Write clear documentation** including README files, API documentation (using tools like Sphinx or FastAPI's automatic docs), and inline docstrings following conventions.

**Containerize your application** using Docker with multi-stage builds, proper base images, and security scanning. Use docker-compose for local development environments.

**Plan for scalability** by designing stateless services, implementing proper caching, database optimization, and considering microservices architecture for complex applications.

These practices become increasingly important as your application grows in complexity and team size. Start with the fundamentals and gradually adopt more sophisticated patterns as your needs evolve.

## Finally

**Dead code** should never be included in the application
**Unused imports** should never be included in the application
**Centralization, centralization, centralization,** make sure to centralize as much logic as possible so that junior engineers with no knowledge of the project can easily maintain this code