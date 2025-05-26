import argparse
import asyncio
import os
import io
import tarfile
import hashlib
import base64
import tempfile
import shutil
import csv
import json
from datetime import date
from asyncio import Queue
from typing import Optional

import aiohttp

from .client import GitHubClient
from .repository import RepoRepository
from .models import Repo, RepoStats, RepoArchive, RepoFileIndex
from .config import settings

def parse_args():
    p = argparse.ArgumentParser(description="Crawl GitHub repos + bundle code")
    p.add_argument("--repos",  type=int, default=settings.max_repos,
                   help="Number of repos to crawl")
    p.add_argument("--outdir", type=str, default="data/repos",
                   help="Directory to write tar.gz archives")
    p.add_argument("--stars-only", action="store_true",
                   help="Only collect star counts, skip file archiving (faster)")
    p.add_argument("--export-csv", type=str,
                   help="Export star data to CSV file")
    p.add_argument("--export-json", type=str,
                   help="Export star data to JSON file")
    p.add_argument("--production", action="store_true",
                   help="Run in production mode with 100k repositories")
    # Matrix partitioning arguments for GitHub Actions
    p.add_argument("--matrix-total", type=int, default=1,
                   help="Total number of matrix jobs (e.g., 40 for GitHub Actions)")
    p.add_argument("--matrix-index", type=int, default=0,
                   help="Current matrix job index (0-based, e.g., 0-39)")
    p.add_argument("--partition-size", type=int, default=2500,
                   help="Number of repositories per partition (100k/40 = 2500)")
    # Alphabetical filtering arguments
    p.add_argument("--alphabet-filter", type=str,
                   help="Filter repositories by owner name starting with specific characters (e.g., 'a-c' or 'abc')")
    return p.parse_args()

def bundle_and_index(repo_id: int, fetched_date: date, files: list[dict], outdir: str):
    os.makedirs(outdir, exist_ok=True)
    name = f"{repo_id}-{fetched_date.isoformat()}.tar.gz"
    path = os.path.join(outdir, name)

    indexes = []
    successful_files = 0
    error_files = 0
    
    with tarfile.open(path, "w:gz") as tf:
        for f in files:
            try:
                content = f["content"]
                
                # Handle different content types from git clone
                if content == "[BINARY_FILE]":
                    # Skip binary files in archive but log them
                    print(f"Skipping binary file: {f['path']}")
                    continue
                elif content.startswith("[BINARY_BASE64]"):
                    # Extract base64 content and decode for storage
                    base64_content = content[15:]  # Remove prefix
                    data = base64.b64decode(base64_content)
                elif content.startswith("[ERROR_DECODING]") or f.get("error", False):
                    # Store error info as text
                    data = content.encode("utf-8")
                    error_files += 1
                else:
                    # Regular text content
                    data = content.encode("utf-8")
                
                sha = hashlib.sha256(data).hexdigest()
                indexes.append(RepoFileIndex(
                    repo_id=repo_id,
                    fetched_date=fetched_date,
                    path=f["path"],
                    content_sha=sha
                ))
                
                info = tarfile.TarInfo(name=f["path"])
                info.size = len(data)
                tf.addfile(info, fileobj=io.BytesIO(data))
                
                if not f.get("error", False):
                    successful_files += 1
                    
            except Exception as e:
                print(f"Error processing file {f.get('path', 'unknown')}: {e}")
                error_files += 1

    print(f"Archive created: {path} ({successful_files} files, {error_files} errors)")
    return path, indexes

async def export_stars_csv(repo_repo: RepoRepository, filename: str):
    """Export repository star data to CSV format"""
    print(f"Exporting star data to CSV: {filename}")
    
    # Get star data from database
    async with repo_repo.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT r.owner, r.name, rs.stars, rs.fetched_date 
            FROM repo r 
            JOIN repo_stats rs ON r.id = rs.repo_id 
            ORDER BY rs.stars DESC
        """)
    
    # Write to CSV
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['owner', 'name', 'stars', 'fetched_date'])
        for row in rows:
            writer.writerow([row['owner'], row['name'], row['stars'], row['fetched_date']])
    
    print(f"Exported {len(rows)} repositories to {filename}")

async def export_stars_json(repo_repo: RepoRepository, filename: str):
    """Export repository star data to JSON format"""
    print(f"Exporting star data to JSON: {filename}")
    
    # Get star data from database
    async with repo_repo.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT r.owner, r.name, rs.stars, rs.fetched_date 
            FROM repo r 
            JOIN repo_stats rs ON r.id = rs.repo_id 
            ORDER BY rs.stars DESC
        """)
    
    # Convert to JSON-serializable format
    data = []
    for row in rows:
        data.append({
            'owner': row['owner'],
            'name': row['name'], 
            'stars': row['stars'],
            'fetched_date': row['fetched_date'].isoformat() if row['fetched_date'] else None
        })
    
    # Write to JSON
    with open(filename, 'w', encoding='utf-8') as jsonfile:
        json.dump(data, jsonfile, indent=2, ensure_ascii=False)
    
    print(f"Exported {len(rows)} repositories to {filename}")

async def run():
    args = parse_args()
    
    # Handle matrix partitioning for GitHub Actions
    if args.matrix_total > 1:
        # Calculate partition boundaries
        partition_start = args.matrix_index * args.partition_size
        partition_end = min((args.matrix_index + 1) * args.partition_size, 100000)
        settings.max_repos = partition_end - partition_start
        
        print(f"🔧 Matrix Job {args.matrix_index + 1}/{args.matrix_total}")
        print(f"📊 Processing repositories {partition_start + 1}-{partition_end} ({settings.max_repos} repos)")
        print(f"🎯 Partition size: {args.partition_size} repos per runner")
    elif args.production:
        settings.max_repos = 100000
        print("🚀 Production mode: Configured for 100,000 repositories")
        print("⚠️  This will take approximately 2.75 hours with standard rate limits")
    else:
        settings.max_repos = args.repos

    if args.alphabet_filter:
        print(f"🔤 Alphabetical filtering enabled: {args.alphabet_filter}")

    client = GitHubClient()
    repo_repo = RepoRepository()
    await repo_repo.init()

    if args.stars_only:
        # Original fast path for stars-only mode
        raw = await client.crawl(alphabet_filter=args.alphabet_filter)
        today = date.today()

        repos = [
            Repo(id=r["id"], name=r["name"], owner=r["owner"],
                 url=r["url"], created_at=r["created_at"], alphabet_partition=args.alphabet_filter)
            for r in raw
        ]
        stats = [
            RepoStats(repoId=r["id"], fetched_date=today, stars=r["stars"])
            for r in raw
        ]

        await repo_repo.upsert_repos(repos)
        await repo_repo.insert_stats(stats)
        
        print(f"✅ Stars-only mode: Successfully collected {len(repos)} repositories with star counts")
        if args.alphabet_filter:
            print(f"🔤 Filtered by alphabet: {args.alphabet_filter}")
        print(f"Skipping file archiving for optimal performance with large datasets")
    else:
        # Optimized pipeline mode for full archiving
        await run_pipelined_archiving(client, repo_repo, args)

    # Export data if requested
    if args.export_csv:
        await export_stars_csv(repo_repo, args.export_csv)
    
    if args.export_json:
        await export_stars_json(repo_repo, args.export_json)

    await repo_repo.close()

async def run_pipelined_archiving(client: GitHubClient, repo_repo: RepoRepository, args):
    """Run GraphQL fetching and git cloning in parallel using a pipeline approach"""
    today = date.today()
    
    # Create queues for pipeline stages
    repo_queue = Queue(maxsize=500)
    completed_repos = []
    
    # Calculate partition offset for matrix jobs
    partition_offset = 0
    if args.matrix_total > 1:
        partition_offset = args.matrix_index * args.partition_size
        print(f"🎯 Matrix partition: Starting from repository #{partition_offset + 1}")
    
    print(f"🚀 Starting pipelined processing for {settings.max_repos} repositories")
    print(f"📊 GraphQL batches will feed git clone workers in parallel")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using temporary directory: {temp_dir}")
        
        # Start the GraphQL producer
        producer_task = asyncio.create_task(
            graphql_producer(client, repo_queue, repo_repo, today, partition_offset, args.alphabet_filter)
        )
        
        # Start multiple git clone consumers
        max_concurrent_clones = 250
        consumer_tasks = []
        
        for i in range(max_concurrent_clones):
            task = asyncio.create_task(
                git_clone_consumer(
                    repo_queue, 
                    client, 
                    repo_repo, 
                    temp_dir, 
                    today, 
                    args.outdir,
                    completed_repos,
                    worker_id=i
                )
            )
            consumer_tasks.append(task)
        
        # Wait for producer to finish
        await producer_task
        
        # Signal consumers that no more work is coming
        for _ in range(max_concurrent_clones):
            await repo_queue.put(None)  # Sentinel value
        
        # Wait for all consumers to finish
        await asyncio.gather(*consumer_tasks)
        
        print(f"✅ Pipeline completed: {len(completed_repos)} repositories processed")

async def graphql_producer(client: GitHubClient, repo_queue: Queue, repo_repo: RepoRepository, today: date, partition_offset: int = 0, alphabet_filter: Optional[str] = None):
    """Fetch repositories via GraphQL and feed them to the processing queue"""
    repos = []
    after = None
    batch_count = 0
    
    async with aiohttp.ClientSession() as session:
        # Skip to partition starting point if needed
        if partition_offset > 0:
            after = await client.skip_to_partition(session, partition_offset, alphabet_filter)
        while len(repos) < settings.max_repos:
            try:
                batch_count += 1
                print(f"📡 GraphQL Batch {batch_count}: Fetching repositories...")
                
                search = await client.fetch_repos(session, after, alphabet_filter)
                batch_repos = []
                
                for node in search["nodes"]:
                    repo_data = {
                        "id": node["databaseId"],
                        "name": node["name"],
                        "owner": node["owner"]["login"],
                        "url": node["url"],
                        "created_at": node["createdAt"],
                        "stars": node["stargazerCount"]
                    }
                    batch_repos.append(repo_data)
                    repos.append(repo_data)
                
                # Store repository metadata immediately
                repo_models = [
                    Repo(id=r["id"], name=r["name"], owner=r["owner"],
                         url=r["url"], created_at=r["created_at"], alphabet_partition=alphabet_filter)
                    for r in batch_repos
                ]
                stats_models = [
                    RepoStats(repoId=r["id"], fetched_date=today, stars=r["stars"])
                    for r in batch_repos
                ]
                
                await repo_repo.upsert_repos(repo_models)
                await repo_repo.insert_stats(stats_models)
                
                # Feed repositories to the processing queue
                for repo_data in batch_repos:
                    await repo_queue.put(repo_data)
                
                print(f"📊 Added {len(batch_repos)} repos to processing queue (total: {len(repos)})")
                
                if not search["pageInfo"]["hasNextPage"]:
                    print("📡 GraphQL: No more pages available")
                    break
                    
                after = search["pageInfo"]["endCursor"]
                
                # Small delay to be respectful to API
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"❌ GraphQL batch {batch_count} error: {e}")
                if repos:
                    print(f"Continuing with {len(repos)} repositories collected so far")
                    break
                else:
                    raise

async def git_clone_consumer(repo_queue: Queue, client: GitHubClient, repo_repo: RepoRepository, 
                           temp_dir: str, today: date, outdir: str, completed_repos: list, worker_id: int):
    """Consumer that processes repositories from the queue"""
    processed_count = 0
    
    while True:
        try:
            # Get next repository from queue
            repo_data = await repo_queue.get()
            
            # Check for sentinel value (end of work)
            if repo_data is None:
                print(f"🔧 Worker {worker_id}: Shutting down after processing {processed_count} repositories")
                break
            
            print(f"🔧 Worker {worker_id}: Processing {repo_data['owner']}/{repo_data['name']}")
            
            try:
                # Clone and archive the repository
                files = await client.crawl_files_for_repo_with_git(repo_data, temp_dir)
                archive_path, indexes = bundle_and_index(repo_data["id"], today, files, outdir)
                rel = os.path.relpath(archive_path)
                
                # Store archive and index info
                await repo_repo.insert_archive(RepoArchive(
                    repo_id=repo_data["id"],
                    fetched_date=today,
                    archive_path=rel
                ))
                await repo_repo.upsert_file_index(indexes)
                
                completed_repos.append(repo_data)
                processed_count += 1
                
                print(f"✅ Worker {worker_id}: Completed {repo_data['owner']}/{repo_data['name']} ({processed_count} total)")
                
            except Exception as e:
                print(f"❌ Worker {worker_id}: Failed to process {repo_data['owner']}/{repo_data['name']}: {e}")
            
            # Mark task as done
            repo_queue.task_done()
            
        except Exception as e:
            print(f"❌ Worker {worker_id}: Queue processing error: {e}")
            break

if __name__ == "__main__":
    asyncio.run(run())
