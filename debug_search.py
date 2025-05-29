#!/usr/bin/env python3
"""
Debug script to test GitHub search queries and understand why the crawler
is collecting 0 repositories in GitHub Actions.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, '.')

from crawler.client import GitHubClient
from crawler.search_strategy import SimpleSearchStrategy
from crawler.config import settings

async def debug_search_queries():
    """Test search queries to understand why they return 0 results."""
    
    print("🔍 GitHub Search Query Debug Tool")
    print("=" * 50)
    
    # Check environment
    token = os.getenv('GITHUB_TOKEN', settings.github_token)
    print(f"GitHub Token Length: {len(token)}")
    print(f"Max Repos Setting: {settings.max_repos}")
    print()
    
    if not token or token == "dummy_token_for_validation":
        print("❌ No valid GitHub token found!")
        print("Please set GITHUB_TOKEN environment variable")
        return
    
    strategy = SimpleSearchStrategy()
    
    # Test different matrix configurations
    test_cases = [
        (1, 0),    # Single job
        (100, 0),  # Matrix job 0
        (100, 10), # Matrix job 10
        (100, 50), # Matrix job 50
        (100, 99), # Matrix job 99
    ]
    
    async with GitHubClient(token) as client:
        # Test connection first
        if not await client.test_connection():
            print("❌ GitHub API connection failed!")
            return
        
        for matrix_total, matrix_index in test_cases:
            print(f"\n🎯 Testing Matrix {matrix_index}/{matrix_total}")
            print("-" * 30)
            
            queries = strategy.generate_queries(matrix_index, matrix_total)
            
            for i, query in enumerate(queries):
                print(f"\nQuery {i+1}: {query.query_string}")
                print(f"Description: {query.description}")
                
                try:
                    # Test the query
                    result = await client.search_repositories(query)
                    
                    repo_count = result.get('repositoryCount', 0)
                    returned_repos = len(result.get('repositories', []))
                    
                    print(f"✅ Total available: {repo_count}")
                    print(f"✅ Returned in page: {returned_repos}")
                    
                    if returned_repos > 0:
                        # Show sample repository
                        sample_repo = result['repositories'][0]
                        print(f"   Sample: {sample_repo.name_with_owner} ({sample_repo.stars} ⭐)")
                    
                    # Test if we can paginate
                    page_info = result.get('pageInfo', {})
                    has_next = page_info.get('hasNextPage', False)
                    print(f"   Has more pages: {has_next}")
                    
                except Exception as e:
                    print(f"❌ Query failed: {e}")
                
                # Only test first 2 queries per matrix to avoid rate limits
                if i >= 1:
                    break
                    
            # Only test first 3 matrix configurations to avoid rate limits
            if len([tc for tc in test_cases if test_cases.index(tc) <= test_cases.index((matrix_total, matrix_index))]) >= 3:
                break

async def test_simple_queries():
    """Test very basic queries that should definitely return results."""
    
    print("\n🔍 Testing Simple Queries")
    print("=" * 30)
    
    token = os.getenv('GITHUB_TOKEN', settings.github_token)
    
    simple_queries = [
        "is:public stars:>1000 sort:stars",
        "is:public language:javascript stars:>100",
        "is:public language:python stars:>100", 
        "is:public created:2024-01-01..2024-12-31 stars:>10",
        "is:public stars:1..10 sort:updated",
    ]
    
    async with GitHubClient(token) as client:
        for query_string in simple_queries:
            print(f"\n🔍 Testing: {query_string}")
            
            from crawler.domain import SearchQuery
            query = SearchQuery(
                query_string=query_string,
                description="Simple test query",
                expected_results=100
            )
            
            try:
                result = await client.search_repositories(query)
                repo_count = result.get('repositoryCount', 0)
                returned_repos = len(result.get('repositories', []))
                
                print(f"   Total: {repo_count}, Returned: {returned_repos}")
                
                if returned_repos > 0:
                    sample = result['repositories'][0]
                    print(f"   Sample: {sample.name_with_owner} ({sample.stars} ⭐)")
                else:
                    print("   ❌ No repositories returned!")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")

async def main():
    """Main debug function."""
    print(f"🚀 Starting debug at {datetime.now()}")
    
    try:
        await test_simple_queries()
        await debug_search_queries()
        
        print("\n✅ Debug completed!")
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
