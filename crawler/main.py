import argparse
import asyncio
import asyncpg
import json
import os
from datetime import datetime, timezone

from .client import GitHubClient
from .config import settings

def parse_github_datetime(dt_str):
    """Parse GitHub datetime string to timezone-naive datetime for PostgreSQL"""
    if not dt_str:
        return None
    # Convert Z to +00:00, parse to timezone-aware, then convert to naive UTC
    dt_aware = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    return dt_aware.astimezone(timezone.utc).replace(tzinfo=None)

def parse_args():
    p = argparse.ArgumentParser(description="Crawl GitHub repos for star counts")
    p.add_argument("--repos", type=int, default=settings.max_repos,
                   help="Number of repos to crawl")
    p.add_argument("--matrix-total", type=int, default=1,
                   help="Total number of matrix jobs")
    p.add_argument("--matrix-index", type=int, default=0,
                   help="Current matrix job index (0-based)")
    return p.parse_args()

async def store_repositories(repos: list, matrix_index: int):
    """Store repositories with comprehensive metadata in the enhanced database schema"""
    conn = await asyncpg.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        user=os.getenv('POSTGRES_USER', 'crawler_user'),
        password=os.getenv('POSTGRES_PASSWORD', 'crawler_password'),
        database=os.getenv('POSTGRES_DB', 'github_crawler')
    )
    
    # Create table schema using migration-compatible format
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS repo (
            id BIGINT PRIMARY KEY,
            name TEXT NOT NULL,
            owner TEXT NOT NULL,
            url TEXT NOT NULL,
            created_at TIMESTAMP,
            alphabet_partition VARCHAR(100),
            name_with_owner TEXT
        )
    ''')
    
    # Create repo_stats table for star counts over time
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS repo_stats (
            repo_id BIGINT NOT NULL REFERENCES repo(id) ON DELETE CASCADE,
            fetched_date DATE NOT NULL,
            stars INT NOT NULL,
            PRIMARY KEY(repo_id, fetched_date)
        )
    ''')
    
    # Create indexes for performance
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_repo_stars ON repo (id)') 
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_repo_name_with_owner ON repo (name_with_owner)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_repo_alphabet_partition ON repo (alphabet_partition)')
    
    # Insert repositories into repo table and stars into repo_stats
    current_date = datetime.now(timezone.utc).date()
    
    for repo in repos:
        try:
            # Insert/update repo
            await conn.execute('''
                INSERT INTO repo 
                (id, name, owner, url, created_at, name_with_owner, alphabet_partition)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (id) DO UPDATE SET
                    name_with_owner = EXCLUDED.name_with_owner,
                    alphabet_partition = EXCLUDED.alphabet_partition
            ''', 
            repo["id"], 
            repo["name"], 
            repo["owner"],
            repo["url"], 
            parse_github_datetime(repo.get("created_at")),
            repo["name_with_owner"],
            f"matrix_{matrix_index}")
            
            # Insert star count into repo_stats
            await conn.execute('''
                INSERT INTO repo_stats (repo_id, fetched_date, stars)
                VALUES ($1, $2, $3)
                ON CONFLICT (repo_id, fetched_date) DO UPDATE SET
                    stars = EXCLUDED.stars
            ''',
            repo["id"],
            current_date,
            repo["stars"])
            
        except Exception as e:
            print(f"⚠️ Error inserting repo {repo['id']}: {e}")
    
    await conn.close()
    print(f"✅ Stored {len(repos)} repositories in repo table with star data in repo_stats")

async def run():
    args = parse_args()
    
    print(f"🚀 Matrix Job {args.matrix_index + 1}/{args.matrix_total}")
    print(f"🎯 Target: {settings.max_repos} repositories")
    print(f"🧠 Memory: Optimized for large-scale collection")
    print(f"🔑 GitHub token configured: {'Yes' if settings.github_token and settings.github_token != 'dummy_token_for_validation' else 'No'}")

    # Validate GitHub token
    if not settings.github_token or settings.github_token == 'dummy_token_for_validation':
        print("❌ ERROR: GitHub token not properly configured!")
        print("Expected environment variable: GITHUB_TOKEN")
        print(f"Current token value: '{settings.github_token}'")
        return 0

    # Performance tracking
    start_time = datetime.now()
    
    try:
        client = GitHubClient()
        
        # Test GitHub API connection first
        print("🔍 Testing GitHub API connection...")
        if not await client.test_connection():
            print("❌ FATAL: GitHub API connection failed!")
            return 0

        # Crawl repositories using enhanced multi-dimensional partitioning
        repos = await client.crawl(matrix_total=args.matrix_total, matrix_index=args.matrix_index)
        
        if not repos:
            print("⚠️ WARNING: No repositories were collected!")
            print("This could indicate:")
            print("  - GitHub API authentication issues")
            print("  - Rate limiting")
            print("  - Search query returned no results")
            print("  - Network connectivity issues")
            return 0
        
        # Calculate performance metrics
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        repos_per_second = len(repos) / duration if duration > 0 else 0
        
        print(f"⏱️ Collection completed in {duration:.2f} seconds")
        print(f"🚀 Rate: {repos_per_second:.2f} repositories/second")
        
        # Store in database
        await store_repositories(repos, args.matrix_index)
        
        print(f"🎉 Matrix job {args.matrix_index} completed successfully!")
        print(f"📊 Final count: {len(repos)} unique repositories")
        
        return len(repos)
        
    except Exception as e:
        print(f"❌ FATAL ERROR in crawler: {e}")
        import traceback
        traceback.print_exc()
        return 0

if __name__ == "__main__":
    asyncio.run(run())
