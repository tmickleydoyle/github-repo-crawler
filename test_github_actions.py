#!/usr/bin/env python3
"""
Test script to simulate GitHub Actions environment and troubleshoot
why the crawler collects 0 repositories in CI.
"""

import asyncio
import os
import sys
import subprocess
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, '.')

async def test_github_actions_simulation():
    """Simulate the exact GitHub Actions environment and command."""
    
    print("🔍 GitHub Actions Environment Simulation")
    print("=" * 50)
    
    # Set environment variables exactly like GitHub Actions
    os.environ["MAX_REPOS"] = "1000"
    os.environ["POSTGRES_HOST"] = "localhost"
    os.environ["POSTGRES_PORT"] = "5432"
    os.environ["POSTGRES_DB"] = "crawler"
    os.environ["POSTGRES_USER"] = "crawler_user"
    os.environ["POSTGRES_PASSWORD"] = "crawler_password"
    
    # Ensure GitHub token is set
    if not os.getenv("GITHUB_TOKEN"):
        print("❌ Please set GITHUB_TOKEN environment variable first")
        return
        
    print(f"GitHub Token Length: {len(os.getenv('GITHUB_TOKEN', ''))}")
    print(f"MAX_REPOS: {os.getenv('MAX_REPOS')}")
    print(f"Matrix simulation: job 0 of 100")
    print()
    
    # Test the exact command that GitHub Actions runs
    cmd = [
        sys.executable, "-m", "crawler.main",
        "--repos", "1000",
        "--matrix-total", "100", 
        "--matrix-index", "0"
    ]
    
    print(f"🚀 Running command: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        # Run the command and capture output
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        print(f"\nReturn code: {result.returncode}")
        
        if result.returncode != 0:
            print("❌ Command failed!")
        else:
            print("✅ Command succeeded!")
            
    except subprocess.TimeoutExpired:
        print("⏱️ Command timed out after 5 minutes")
    except Exception as e:
        print(f"❌ Error running command: {e}")

async def test_direct_crawler_call():
    """Test calling the crawler directly without subprocess."""
    
    print("\n🔍 Direct Crawler Call Test")
    print("=" * 30)
    
    # Set environment exactly like GitHub Actions
    os.environ["MAX_REPOS"] = "1000"
    
    from crawler.main import run
    from crawler.config import settings
    
    print(f"Settings max_repos: {settings.max_repos}")
    print(f"ENV MAX_REPOS: {os.getenv('MAX_REPOS')}")
    
    # Mock sys.argv to simulate the GitHub Actions command
    original_argv = sys.argv
    sys.argv = [
        "crawler.main",
        "--repos", "1000",
        "--matrix-total", "100",
        "--matrix-index", "0"
    ]
    
    try:
        await run()
        print("✅ Direct crawler call succeeded!")
    except Exception as e:
        print(f"❌ Direct crawler call failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sys.argv = original_argv

async def test_search_strategy_matrix():
    """Test the search strategy for matrix job 0 specifically."""
    
    print("\n🔍 Matrix Job 0 Search Strategy Test")
    print("=" * 40)
    
    from crawler.search_strategy import SimpleSearchStrategy
    
    strategy = SimpleSearchStrategy()
    queries = strategy.generate_queries(matrix_index=0, matrix_total=100)
    
    print(f"Generated {len(queries)} queries for matrix job 0/100:")
    for i, query in enumerate(queries):
        print(f"  {i+1}. {query.query_string}")
        print(f"     Description: {query.description}")
        print(f"     Expected: {query.expected_results}")
    
    # Test these specific queries
    from crawler.client import GitHubClient
    
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ No GitHub token available for testing")
        return
        
    async with GitHubClient(token) as client:
        if not await client.test_connection():
            print("❌ GitHub API connection failed")
            return
            
        for i, query in enumerate(queries[:2]):  # Test first 2 queries
            print(f"\n🔍 Testing query {i+1}: {query.query_string}")
            
            try:
                result = await client.search_repositories(query)
                repo_count = result.get('repositoryCount', 0)
                returned_repos = len(result.get('repositories', []))
                
                print(f"   ✅ Total: {repo_count}, Returned: {returned_repos}")
                
                if returned_repos > 0:
                    sample = result['repositories'][0]
                    print(f"   Sample: {sample.name_with_owner} ({sample.stars} ⭐)")
                else:
                    print("   ❌ No repositories returned!")
                    
            except Exception as e:
                print(f"   ❌ Query failed: {e}")

async def main():
    """Main test function."""
    
    print("🚀 GitHub Actions Troubleshooting Suite")
    print("🚀 Running comprehensive tests to identify the issue")
    print()
    
    try:
        await test_search_strategy_matrix()
        await test_direct_crawler_call()
        await test_github_actions_simulation()
        
        print("\n" + "=" * 50)
        print("✅ All tests completed!")
        print("Check the output above to identify any issues.")
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
