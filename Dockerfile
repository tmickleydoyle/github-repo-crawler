# Multi-stage Docker build for GitHub Crawler

# Stage 1: Build dependencies
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install dependencies
COPY pyproject.toml ./
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e .

# Stage 2: Runtime
FROM python:3.11-slim as runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r crawler && useradd -r -g crawler crawler

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=crawler:crawler crawler/ ./crawler/
COPY --chown=crawler:crawler alembic/ ./alembic/
COPY --chown=crawler:crawler alembic.ini ./
COPY --chown=crawler:crawler migrations/ ./migrations/

# Create necessary directories
RUN mkdir -p /app/data /app/logs && \
    chown -R crawler:crawler /app/data /app/logs

# Switch to non-root user
USER crawler

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
ENTRYPOINT ["python", "-m", "crawler.main"]

# Stage 3: Development (optional)
FROM runtime as development

# Switch back to root for development tools installation
USER root

# Install development dependencies
COPY pyproject.toml ./
RUN pip install -e ".[dev]"

# Install additional development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    make \
    && rm -rf /var/lib/apt/lists/*

# Switch back to crawler user
USER crawler

# Override entrypoint for development
ENTRYPOINT ["/bin/bash"]