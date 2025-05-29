# Makefile for GitHub Crawler Project
# 
# This Makefile provides common tasks for development, testing, and deployment
# of the GitHub crawler application following clean architecture principles.

.PHONY: help install test test-unit test-integration test-coverage lint format type-check quality run clean docker-build docker-run

# Default target
help:
	@echo "GitHub Crawler - Available Commands:"
	@echo ""
	@echo "Development Commands:"
	@echo "  install          Install dependencies"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-coverage    Run tests with coverage report"
	@echo "  lint             Run code linting"
	@echo "  format           Format code with black"
	@echo "  type-check       Run type checking with mypy"
	@echo "  quality          Run all quality checks (lint, type, test)"
	@echo ""
	@echo "Runtime Commands:"
	@echo "  run              Run the crawler locally"
	@echo "  docker-build     Build Docker image"
	@echo "  docker-run       Run crawler in Docker"
	@echo ""
	@echo "Utility Commands:"
	@echo "  clean            Clean up temporary files"

# Install dependencies
install:
	@echo "🔧 Installing dependencies..."
	pip install -r requirements.txt
	@echo "✅ Dependencies installed!"

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

# Lint code
lint:
	@echo "🔍 Running code linting..."
	python -m flake8 crawler/ tests/ --count --statistics
	@echo "✅ Linting completed!"

# Format code
format:
	@echo "🎨 Formatting code..."
	python -m black crawler/ tests/ --line-length=88
	@echo "✅ Code formatted!"

# Type checking
type-check:
	@echo "🔍 Running type checking..."
	python -m mypy crawler/ tests/ --ignore-missing-imports
	@echo "✅ Type checking completed!"

# Run comprehensive CI simulation
ci-sim:
	@echo "🚀 Running CI simulation..."
	./test-ci.sh

# Run all quality checks (matches CI)
quality:
	@echo "🎯 Running comprehensive quality checks..."
	@echo "1️⃣ Linting..."
	@python -m flake8 crawler/ tests/ --count --statistics
	@echo "2️⃣ Type checking..."
	@python -m mypy crawler/ tests/ --ignore-missing-imports
	@echo "3️⃣ Code formatting check..."
	@python -m black --check crawler/ tests/ --line-length=88
	@echo "4️⃣ Running tests..."
	@python -m pytest tests/ -v --tb=short
	@echo "🎉 All quality checks passed!"

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
	@echo "✅ Cleanup completed!"

# Build Docker image
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t github-crawler:latest .
	@echo "✅ Docker image built!"

# Run in Docker
docker-run:
	@echo "🐳 Running crawler in Docker..."
	docker-compose up --build
	@echo "✅ Docker run completed!"

# Development setup (install + quality checks)
dev-setup: install quality
	@echo "🎉 Development environment ready!"

# CI/CD pipeline simulation
ci: install quality test-coverage
	@echo "🎯 CI pipeline completed successfully!"

# Quick development test (fast feedback loop)
dev-test: test-unit lint
	@echo "⚡ Quick development tests passed!"
