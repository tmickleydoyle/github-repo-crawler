# Makefile for GitHub Crawler Project
#
# This Makefile provides common tasks for development, testing, and deployment
# of the GitHub crawler application following clean architecture principles.

.PHONY: help install install-dev test test-unit test-integration test-coverage lint format type-check quality run clean docker-build docker-run db-migrate db-upgrade db-downgrade

# Default target
help:
	@echo "GitHub Crawler - Available Commands:"
	@echo ""
	@echo "Development Commands:"
	@echo "  install          Install production dependencies"
	@echo "  install-dev      Install all dependencies including dev"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-coverage    Run tests with coverage report"
	@echo "  lint             Run code linting with ruff"
	@echo "  format           Format code with ruff"
	@echo "  type-check       Run type checking with mypy"
	@echo "  quality          Run all quality checks (lint, type, test)"
	@echo ""
	@echo "Database Commands:"
	@echo "  db-migrate       Create a new database migration"
	@echo "  db-upgrade       Apply database migrations"
	@echo "  db-downgrade     Rollback database migrations"
	@echo ""
	@echo "Runtime Commands:"
	@echo "  run              Run the crawler locally"
	@echo "  docker-build     Build Docker image"
	@echo "  docker-run       Run crawler in Docker"
	@echo ""
	@echo "Utility Commands:"
	@echo "  clean            Clean up temporary files"

# Install production dependencies
install:
	@echo "🔧 Installing production dependencies..."
	pip install --upgrade pip
	pip install -e .
	@echo "✅ Dependencies installed!"

# Install all dependencies including development
install-dev:
	@echo "🔧 Installing all dependencies including development..."
	pip install --upgrade pip
	pip install -e ".[dev,docs]"
	pre-commit install
	@echo "✅ All dependencies installed!"

# Run all tests
test:
	@echo "🧪 Running all tests..."
	python -m pytest tests/ -v --tb=short
	@echo "✅ All tests completed!"

# Run unit tests only
test-unit:
	@echo "🧪 Running unit tests..."
	python -m pytest tests/ -v -m "not integration" --tb=short
	@echo "✅ Unit tests completed!"

# Run integration tests only
test-integration:
	@echo "🧪 Running integration tests..."
	python -m pytest tests/ -v -m "integration" --tb=short
	@echo "✅ Integration tests completed!"

# Run tests with coverage
test-coverage:
	@echo "🧪 Running tests with coverage..."
	python -m pytest tests/ --cov=crawler --cov-report=html --cov-report=term-missing -v
	@echo "✅ Coverage report generated in htmlcov/"

# Lint code with ruff
lint:
	@echo "🔍 Running code linting with ruff..."
	python -m ruff check crawler/ tests/
	@echo "✅ Linting completed!"

# Format code with ruff
format:
	@echo "🎨 Formatting code with ruff..."
	python -m ruff format crawler/ tests/
	python -m ruff check --fix crawler/ tests/
	@echo "✅ Code formatted!"

# Type checking with mypy
type-check:
	@echo "🔍 Running type checking..."
	python -m mypy crawler/ --ignore-missing-imports --strict
	@echo "✅ Type checking completed!"

# Run all quality checks (matches CI)
quality:
	@echo "🎯 Running comprehensive quality checks..."
	@echo "1️⃣ Linting..."
	@python -m ruff check crawler/ tests/
	@echo "2️⃣ Type checking..."
	@python -m mypy crawler/ --ignore-missing-imports --strict
	@echo "3️⃣ Code formatting check..."
	@python -m ruff format --check crawler/ tests/
	@echo "4️⃣ Running tests..."
	@python -m pytest tests/ -v --tb=short
	@echo "🎉 All quality checks passed!"

# Database migrations
db-migrate:
	@echo "📝 Creating new database migration..."
	@read -p "Enter migration message: " msg; \
	alembic revision -m "$$msg"
	@echo "✅ Migration created!"

db-upgrade:
	@echo "⬆️ Applying database migrations..."
	alembic upgrade head
	@echo "✅ Migrations applied!"

db-downgrade:
	@echo "⬇️ Rolling back database migration..."
	alembic downgrade -1
	@echo "✅ Migration rolled back!"

# Run the crawler locally
run:
	@echo "🚀 Running GitHub crawler..."
	python -m crawler.main --repos 100 --matrix-total 1 --matrix-index 0

# Clean up temporary files
clean:
	@echo "🧹 Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	@echo "✅ Cleanup completed!"

# Build Docker image
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t github-crawler:latest .
	@echo "✅ Docker image built!"

# Build development Docker image
docker-build-dev:
	@echo "🐳 Building development Docker image..."
	docker build --target development -t github-crawler:dev .
	@echo "✅ Development Docker image built!"

# Run in Docker
docker-run:
	@echo "🐳 Running crawler in Docker..."
	docker-compose up --build
	@echo "✅ Docker run completed!"

# Development setup (install + quality checks)
dev-setup: install-dev quality
	@echo "🎉 Development environment ready!"

# CI/CD pipeline simulation
ci: install quality test-coverage
	@echo "🎯 CI pipeline completed successfully!"

# Quick development test (fast feedback loop)
dev-test: lint test-unit
	@echo "⚡ Quick development tests passed!"

# Update dependencies in pyproject.toml
update-deps:
	@echo "📦 Updating dependencies..."
	pip install --upgrade pip pip-tools
	pip-compile --upgrade pyproject.toml
	@echo "✅ Dependencies updated!"

# Security audit
security:
	@echo "🔒 Running security audit..."
	pip install bandit safety
	bandit -r crawler/ --skip B101
	safety check
	@echo "✅ Security audit completed!"