# GitHub Repository Crawler

A scalable, production-ready GitHub repository crawler designed for discovering and tracking millions of repositories with persistence and deduplication.

## 📋 Project Structure & Organization

Following CLAUDE.md principles with clear separation of concerns:

```
github-crawler-task/
├── crawler/                    # Main application package
│   ├── __init__.py
│   ├── main.py                # Entry point
│   ├── client.py              # GitHub API client
│   ├── config.py              # Configuration management (Pydantic)
│   ├── db_repository.py       # Database operations (Repository pattern)
│   ├── domain.py              # Domain models and types
│   ├── logger.py              # Centralized structured logging
│   └── search_strategy.py     # Search query generation strategies
├── scripts/                   # Utility and setup scripts
│   ├── setup_supabase.py      # Database setup automation
│   ├── check_persistence.py   # Persistence monitoring
│   ├── check_schema.py        # Database schema validation
│   ├── check_supabase_storage.py # Storage diagnostics
│   ├── configure_pipeline.py  # Pipeline configuration
│   ├── debug_connection_safe.py # Connection debugging
│   ├── debug_storage_issue.py # Storage issue analysis
│   └── calculate_scale.py     # Scale analysis
├── tests/                     # Test suite (pytest)
├── .github/workflows/         # CI/CD GitHub Actions
├── docs/                      # Documentation
└── pyproject.toml            # Modern Python packaging
```

## 🚀 Key Features

- **Parallel GraphQL API crawling** using GitHub's GraphQL API v4
- **PostgreSQL database** with optimized schema for efficient updates
- **Rate limit handling** with exponential backoff and retry mechanisms
- **Matrix-based parallel execution** for scalable data collection
- **GitHub Actions CI/CD pipeline** with PostgreSQL service containers
- **Database export functionality** with CSV outputs

### Key Features

- 🚀 **High Performance**: Matrix-based parallel crawling
- 📊 **Scalable Architecture**: Designed to handle 100K+ repositories efficiently
- 🔄 **Retry Mechanisms**: Robust error handling with exponential backoff
- 📈 **Historical Tracking**: Time-series data storage for star count evolution
- 🛡️ **Rate Limit Compliance**: Intelligent rate limiting to respect GitHub API limits
- 🗃️ **Optimized Database**: Efficient schema with proper indexing and conflict resolution

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   GitHub API    │◄───│  Python Crawler  │───►│   PostgreSQL    │
│   (GraphQL v4)  │    │  (Matrix Jobs)   │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  Data Exports   │
                       │  (CSV + SQL)    │
                       └─────────────────┘
```

## 🛠️ Technology Stack

- **Python 3.11+** with asyncio for concurrent operations
- **aiohttp** for async HTTP requests to GitHub API
- **asyncpg** for high-performance PostgreSQL operations
- **Pydantic** for data validation and serialization
- **Tenacity** for retry mechanisms with exponential backoff
- **PostgreSQL 14+** for data storage
- **GitHub Actions** for CI/CD and automated crawling

## 📂 Project Structure

```
github-crawler-task/
├── crawler/                    # Core crawler package
│   ├── __init__.py
│   ├── main.py                # Entry point and orchestration
│   ├── client.py              # GitHub API client with GraphQL
│   ├── config.py              # Configuration management
│   ├── db_diagnostics.py      # Centralized database diagnostics
│   ├── db_repository.py       # Database operations layer
│   ├── domain.py              # Domain models and business logic
│   ├── logger.py              # Structured logging
│   └── search_strategy.py     # Search strategy implementations
├── migrations/                 # Database schema migrations
│   ├── 001_initial_schema.sql
│   ├── 002_add_alphabet_partition.sql
│   ├── 003_expand_language_partition.sql
│   └── 004_add_name_with_owner.sql
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_client.py
│   ├── test_domain.py
│   ├── test_integration.py
│   └── test_search_strategy.py
├── .github/workflows/          # CI/CD pipeline
│   ├── parallel-star-crawler.yml
├── database_exports/           # Generated data exports
├── docker-compose.yml          # Local PostgreSQL setup
├── requirements.txt           # Python dependencies
├── pytest.ini                # Test configuration
├── setup.cfg                 # Development tools configuration
└── README.md                  # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 14+ (or use Docker Compose)
- GitHub Personal Access Token with `repo` scope

### 1. Environment Setup

```bash
# Clone the repository
git clone git@github.com:tmickleydoyle/github-repo-crawler.git
cd github-crawler-task

# Install Python dependencies
pip install -r requirements.txt

# Set up environment variables
export GITHUB_TOKEN="your_github_personal_access_token"
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
export POSTGRES_DB="crawler"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="postgres"
```

### 2. Database Setup

**Option A: Using Docker Compose (Recommended)**
```bash
# Start PostgreSQL container
docker-compose up -d

# Wait for database to be ready
sleep 10
```

**Option B: Local PostgreSQL Installation**
```bash
# Create database (adjust connection details as needed)
createdb crawler

# Run migrations
psql -d crawler -f migrations/001_initial_schema.sql
psql -d crawler -f migrations/002_add_alphabet_partition.sql
```

### 3. Run the Crawler

**Single Job (Development)**
```bash
# Crawl 4000 repositories (default)
python -m crawler.main

# Crawl specific number of repositories
python -m crawler.main --repos 5000
```

**Matrix Jobs (Production)**
```bash
# Run as part of a 10-job matrix (job index 0)
python -m crawler.main --matrix-total 10 --matrix-index 0

# Run different matrix job
python -m crawler.main --matrix-total 10 --matrix-index 1
```

### 4. Validate Setup

```bash
# Run validation script
python scripts/configure_pipeline.py

# Check database health (requires DATABASE_URL)
python -m crawler.db_diagnostics
```

## 🤖 GitHub Actions Usage

This project includes a sophisticated GitHub Actions workflow that implements the requirements from the original specification.

### Running the Full Crawler Pipeline

1. **Navigate to your repository on GitHub**
2. **Go to Actions tab**
3. **Select "Parallel GitHub Star Crawler" workflow**
4. **Click "Run workflow"**
5. **Configure parameters:**
   - **Matrix Size**: Number of parallel jobs (1-200, default: 200)
   - **Max Repos per Job**: Target repositories per job (default: 4000)

### Workflow Parameters

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| `matrix_size` | Number of parallel crawler jobs | 200 | 1-200 |
| `max_repos_per_job` | Target repositories per job | 4000 | 100-5000 |

### Example Configurations

**Quick Test**
```yaml
matrix_size: 10
max_repos_per_job: 500
```

**Production Run**
```yaml
matrix_size: 200
max_repos_per_job: 4000
```

**High-Density Collection**
```yaml
matrix_size: 100
max_repos_per_job: 8000
```

## 📊 What to Expect After GitHub Actions Runs

### 1. **Workflow Execution**

The workflow consists of three main phases:

**Phase 1: Validation**
- Code validation and dependency checks
- GitHub API authentication verification
- Matrix generation for parallel jobs

**Phase 2: Parallel Crawling**
- Multiple jobs running simultaneously
- Real-time progress logging
- Individual job data exports

**Phase 3: Aggregation**
- Data consolidation from all jobs
- Duplicate removal and final exports
- Repository commit with results

### 2. **Generated Artifacts**

After successful execution, you'll find:

**In the Repository:**
```
database_exports/
└── github_repositories_final.csv # CSV export with star data and replace each time to prevent many large files stored in the repo
```

**As GitHub Actions Artifacts:**
- `final-results` - Complete aggregated data
- `crawler-job-N` - Individual job outputs (N = job index)

### 3. **Expected Data Structure**

**CSV Output Format** (`github_repositories_final.csv`):
```csv
id,name,name_with_owner,url,created_at,stars,crawled_at
123456789,"react","facebook/react","https://github.com/facebook/react","2013-05-24 16:15:54",200000,"2025-05-28"
987654321,"vue","vuejs/vue","https://github.com/vuejs/vue","2013-07-29 03:24:51",195000,"2025-05-28"
```

**Database Schema:**
```sql
-- Repository metadata
repo (id, name, owner, url, created_at, alphabet_partition, name_with_owner)

-- Time-series star data  
repo_stats (repo_id, fetched_date, stars)
```

### 4. **Success Indicators**

✅ **Successful Run:**
- All matrix jobs complete without errors
- Final CSV contains expected number of repositories
- No rate limit violations in logs
- Database exports generated successfully

⚠️ **Partial Success:**
- Some matrix jobs fail but aggregation completes
- Reduced repository count but valid data
- Rate limiting encountered but handled gracefully

❌ **Failed Run:**
- GitHub API authentication issues
- Database connection problems
- Invalid configuration parameters

### 5. **Log Output Examples**

**Successful Job Log:**
```
🚀 Matrix Job 1/200
🎯 Target: 4000 repositories  
🔑 GitHub token length: 40 characters
✅ GitHub API authentication successful
📋 Authenticated as: username
🚦 Rate limit remaining: 4999
🔍 Fetching repositories batch 1/40...
✅ Stored 4000 repositories in repo table with star data
⏱️ Collection completed in 120.45 seconds
🚀 Rate: 33.22 repositories/second
✅ Matrix job 0 completed successfully!
```

**Aggregation Summary:**
```
📊 Aggregation Summary:
  - Total rows processed: 780,000 repos, 780,000 stats
  - Final unique records: 456,789 repos, 456,789 stats  
  - Duplicate repos skipped: 323,211
  - Deduplication rate: 41% overlap between jobs
✅ Total repositories collected: 456,789
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GITHUB_TOKEN` | GitHub Personal Access Token | - | ✅ |
| `POSTGRES_HOST` | PostgreSQL host | localhost | ✅ |
| `POSTGRES_PORT` | PostgreSQL port | 5432 | ✅ |
| `POSTGRES_DB` | Database name | crawler | ✅ |
| `POSTGRES_USER` | Database user | postgres | ✅ |
| `POSTGRES_PASSWORD` | Database password | postgres | ✅ |
| `MAX_REPOS` | Max repositories per job | 4000 | ❌ |

### GitHub Token Setup

1. Go to [GitHub Settings > Developer Settings > Personal Access Tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select scopes: `public_repo` (minimum)
4. Copy the token
5. Add as repository secret named `GITHUB_TOKEN`

## 🏃‍♂️ GitHub Actions Setup

### Repository Secrets

Ensure your repository has the following secret configured:

- `GITHUB_TOKEN` - Your GitHub Personal Access Token

### Workflow Features

- **Automatic PostgreSQL service container** setup
- **Matrix-based parallel execution** with configurable size
- **Rate limit handling** with intelligent backoff
- **Data deduplication** across parallel jobs
- **Automatic artifact upload** and repository commits
- **Comprehensive logging** with progress tracking

### Manual Workflow Dispatch

The workflow can be triggered manually with custom parameters:

1. Navigate to Actions → Parallel GitHub Star Crawler
2. Click "Run workflow"
3. Set desired matrix size and repositories per job
4. Click "Run workflow"

## 📈 Scaling Considerations

### For 500 Million Repositories

As outlined in the original requirements, scaling to 500M repositories would require:

1. **Infrastructure Changes:**
   - Distributed crawler deployment across multiple regions
   - Database sharding by repository characteristics
   - Message queue (Redis/RabbitMQ) for job coordination

2. **Architecture Modifications:**
   - Microservices architecture with separate crawler instances
   - Stream processing (Apache Kafka) to quickly move large volumes of data without unloading mono-CSV files
   - Data lake storage (S3/GCS) for long-term analytics

3. **Performance Optimizations:**
   - Connection pooling with higher limits
   - Caching layer for frequently accessed data

### Schema Evolution

The current schema supports future metadata expansion:

```sql
-- Future tables for additional GitHub data
CREATE TABLE repo_issues (
    id BIGINT PRIMARY KEY,
    repo_id BIGINT REFERENCES repo(id),
    title TEXT,
    state VARCHAR(20),
    created_at TIMESTAMP
);

CREATE TABLE repo_pulls (
    id BIGINT PRIMARY KEY,
    repo_id BIGINT REFERENCES repo(id),
    title TEXT,
    state VARCHAR(20),
    created_at TIMESTAMP
);

CREATE TABLE pull_comments (
    id BIGINT PRIMARY KEY,
    pull_id BIGINT REFERENCES repo_pulls(id),
    body TEXT,
    created_at TIMESTAMP
);
```

## 🐛 Troubleshooting

### Common Issues

**GitHub API Rate Limiting:**
```bash
# Check current rate limit
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     https://api.github.com/rate_limit
```

**Database Connection Issues:**
```bash
# Test PostgreSQL connection
pg_isready -h localhost -p 5432 -U postgres
```

**Token Authentication:**
```bash
# Verify token permissions
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     https://api.github.com/user
```

### Debug Mode

Enable verbose logging:
```bash
export LOG_LEVEL=DEBUG
python -m crawler.main --repos 100
```
