import aiohttp
import asyncio
import time
from typing import Optional, List
from .config import settings

class GitHubClient:
    def __init__(self, token: str = settings.github_token):
        if not token or token == 'dummy_token_for_validation':
            raise ValueError("GitHub token is required and must be valid")
            
        self.graphql_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v4+json",
            "User-Agent": "GitHub-Crawler/1.0"
        }
        print(f"✅ GitHub client initialized with token length: {len(token)}")

    async def test_connection(self) -> bool:
        """Test GitHub API connection and authentication"""
        test_query = '''
        query {
          viewer {
            login
          }
          rateLimit {
            remaining
            resetAt
          }
        }'''
        
        try:
            async with aiohttp.ClientSession() as session:
                response = await self._post(session, self.graphql_url, {"query": test_query})
                if "errors" in response:
                    print(f"❌ GitHub API test failed: {response['errors']}")
                    return False
                    
                viewer_login = response["data"]["viewer"]["login"]
                rate_limit = response["data"]["rateLimit"]
                print(f"✅ GitHub API connection successful")
                print(f"📋 Authenticated as: {viewer_login}")
                print(f"🚦 Rate limit remaining: {rate_limit['remaining']}")
                return True
        except Exception as e:
            print(f"❌ GitHub API connection test failed: {e}")
            return False

    async def _post(self, session: aiohttp.ClientSession, url: str, json: dict):
        """Make a POST request with rate limit and 5xx error handling (with retries)"""
        max_retries = 5
        backoff = 2
        for attempt in range(max_retries):
            try:
                async with session.post(url, json=json, headers=self.headers) as resp:
                    if resp.status == 403:
                        response_text = await resp.text()
                        if "rate limit" in response_text.lower():
                            print("⏱️ Rate limit hit, waiting 60s...")
                            await asyncio.sleep(60)
                            raise aiohttp.ClientResponseError(resp.request_info, resp.history, status=resp.status)
                    if resp.status in {502, 503, 504}:
                        print(f"🔁 GitHub API {resp.status} error, retrying in {backoff ** attempt}s (attempt {attempt+1}/{max_retries})...")
                        await asyncio.sleep(backoff ** attempt)
                        continue
                    await self._rate_limit_pause(resp)
                    if resp.status != 200:
                        resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientError as e:
                print(f"🔁 Network error: {e}, retrying in {backoff ** attempt}s (attempt {attempt+1}/{max_retries})...")
                await asyncio.sleep(backoff ** attempt)
        raise Exception(f"Failed to POST to GitHub API after {max_retries} attempts")

    async def _rate_limit_pause(self, resp: aiohttp.ClientResponse):
        """Pause if we're close to rate limit"""
        remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
        if remaining < 5:
            await asyncio.sleep(1)

    async def search_repositories(self, session: aiohttp.ClientSession, query: str, after: Optional[str] = None) -> List[dict]:
        """Execute a GraphQL search query and return a list of repos with star counts"""
        graphql_query = '''
        query ($searchQuery: String!, $after: String) {
          search(query: $searchQuery, type: REPOSITORY, first: 100, after: $after) {
            pageInfo { 
              endCursor 
              hasNextPage 
            }
            repositoryCount
            nodes {
              ... on Repository {
                databaseId
                name
                url
                createdAt
                stargazerCount
                owner { 
                  login 
                }
              }
            }
          }
        }'''
        variables = {
            "searchQuery": query,
            "after": after
        }
        payload = {"query": graphql_query, "variables": variables}
        try:
            response = await self._post(session, self.graphql_url, payload)
            if "errors" in response:
                print(f"⚠️ GraphQL errors: {response['errors']}")
                # Check for specific error types
                for error in response['errors']:
                    if 'FORBIDDEN' in str(error) or 'Unauthorized' in str(error):
                        raise Exception(f"GitHub API authentication failed: {error}")
                    elif 'RATE_LIMITED' in str(error):
                        print("⏱️ Rate limited by GitHub, waiting...")
                        await asyncio.sleep(60)
                        raise Exception(f"Rate limited: {error}")
                        
                if "data" not in response or not response["data"]:
                    raise Exception(f"GraphQL query failed: {response['errors']}")
            
            if "data" not in response:
                raise Exception(f"No data in GraphQL response: {response}")
                
            search = response["data"]["search"]
            repos = []
            for node in search["nodes"]:
                repos.append({
                    "id": node["databaseId"],
                    "name": node["name"],
                    "name_with_owner": f"{node['owner']['login']}/{node['name']}",
                    "owner": node["owner"]["login"],
                    "url": node["url"],
                    "created_at": node["createdAt"],
                    "stars": node["stargazerCount"]
                })
            return {
                "pageInfo": search["pageInfo"],
                "repositoryCount": search["repositoryCount"],
                "nodes": repos
            }
        except Exception as e:
            print(f"❌ GraphQL query failed for query '{query}': {e}")
            print(f"❌ Query variables: {variables}")
            raise

    def get_search_queries(self, matrix_index: int = 0, matrix_total: int = 1) -> List[str]:
        """Generate search queries that balance specificity with results availability"""
        if matrix_total == 1:
            # Single job: use broad queries
            return [
                "is:public stars:>=1 sort:updated",
                "is:public stars:0 sort:updated", 
                "is:public sort:updated"
            ]
        
        queries = []
        
        # Simplified strategy focusing on language and star distribution
        # Avoid overly restrictive combinations that yield no results
        
        # Popular languages for partitioning
        languages = [
            "javascript", "python", "java", "typescript", "go", "rust", "php", "c",
            "c++", "c#", "shell", "ruby", "kotlin", "swift", "scala", "dart",
            "r", "html", "css", "dockerfile", "yaml", "json", "none"
        ]
        
        # Broader star ranges that are more likely to have results
        star_buckets = [
            "0..5", "6..20", "21..100", "101..500", "501..2000", ">2000"
        ]
        
        # Simple alphabet partitioning (fewer buckets)
        alphabet_ranges = ["a..e", "f..j", "k..o", "p..t", "u..z", "0..9"]
        
        # Use simpler partitioning strategy
        total_languages = len(languages)
        total_stars = len(star_buckets)
        total_alpha = len(alphabet_ranges)
        
        # Calculate indices for this matrix job
        lang_index = matrix_index % total_languages
        star_index = (matrix_index // total_languages) % total_stars
        alpha_index = (matrix_index // (total_languages * total_stars)) % total_alpha
        
        selected_lang = languages[lang_index]
        selected_stars = star_buckets[star_index]
        selected_alpha = alphabet_ranges[alpha_index]
        
        # Build primary query with language and stars (most important filters)
        if selected_lang == "none":
            # Query for repositories without a detected language
            base_query = "is:public language:\"\" OR is:public NOT language:javascript NOT language:python NOT language:java"
        else:
            base_query = f"is:public language:{selected_lang}"
        
        # Add star constraint
        if selected_stars.startswith(">"):
            stars_filter = f"stars:{selected_stars}"
        else:
            stars_filter = f"stars:{selected_stars}"
        
        primary_query = f"{base_query} {stars_filter} sort:updated"
        queries.append(primary_query)
        
        # Add a fallback query with broader scope but different sorting
        fallback_query = f"{base_query} sort:stars"
        queries.append(fallback_query)
        
        # Add a third query focusing on recent activity if we have room
        if selected_lang != "none":
            recent_query = f"is:public language:{selected_lang} pushed:>2023-01-01 sort:updated"
            queries.append(recent_query)
        
        print(f"🎯 Matrix job {matrix_index}: Lang={selected_lang}, Stars={selected_stars}")
        print(f"📊 Generated {len(queries)} queries with broader search criteria")
        
        return queries

    async def crawl(self, matrix_total: int = 1, matrix_index: int = 0) -> List[dict]:
        """Main crawling method - optimized for maximum unique repository collection with parallel page fetching"""
        print(f"🚀 Starting crawl: Matrix job {matrix_index + 1}/{matrix_total}")
        print(f"🎯 Target: {settings.max_repos} repositories")
        
        repos = []
        repo_ids = set()
        target_repos = settings.max_repos
        max_workers = 5  # Number of concurrent requests per query
        semaphore = asyncio.Semaphore(max_workers)
        progress_intervals = [0.1, 0.25, 0.5, 0.75, 0.9]
        last_reported = 0

        async def fetch_pages(search_query):
            queue = asyncio.Queue()
            await queue.put(None)  # Start with no cursor
            local_repos = []
            local_ids = set()
            stop_flag = False

            async def worker():
                nonlocal stop_flag, last_reported, local_repos, local_ids
                async with aiohttp.ClientSession() as session:
                    while not stop_flag and len(repos) < target_repos:
                        try:
                            after = await queue.get()
                            if stop_flag or len(repos) >= target_repos:
                                queue.task_done()
                                break
                            async with semaphore:
                                search_result = await self.search_repositories(session, search_query, after)
                            batch_added = 0
                            batch_duplicates = 0
                            for node in search_result["nodes"]:
                                repo_id = node["id"]
                                if repo_id not in repo_ids and repo_id not in local_ids:
                                    repo = {
                                        "id": repo_id,
                                        "name": node["name"],
                                        "name_with_owner": node["name_with_owner"],
                                        "owner": node["owner"],
                                        "url": node["url"],
                                        "created_at": node["created_at"],
                                        "stars": node["stars"]
                                    }
                                    local_repos.append(repo)
                                    local_ids.add(repo_id)
                                    batch_added += 1
                                else:
                                    batch_duplicates += 1
                            
                            if batch_duplicates > 0:
                                print(f"🔄 Found {batch_duplicates} duplicate repos in batch (skipped)")
                            
                            # Merge local results into global
                            if batch_added > 0:
                                repos.extend(local_repos[-batch_added:])  # Only add new repos
                                repo_ids.update(local_ids)
                                local_repos = local_repos[:-batch_added]  # Remove processed repos
                                local_ids.clear()
                                
                            if len(repos) % 100 == 0 and len(repos) > 0:
                                print(f"📊 Collected {len(repos)} unique repositories so far...")
                                
                            # Progress reporting
                            current_progress = len(repos) / target_repos
                            for threshold in progress_intervals:
                                if current_progress >= threshold and last_reported < threshold:
                                    print(f"📈 Progress milestone: {threshold*100:.0f}% complete ({len(repos)}/{target_repos} repos)")
                                    last_reported = threshold
                                    break
                            # Enqueue next page
                            if search_result["pageInfo"]["hasNextPage"] and len(repos) < target_repos:
                                await queue.put(search_result["pageInfo"]["endCursor"])
                            else:
                                stop_flag = True
                            queue.task_done()
                        except Exception as e:
                            print(f"❌ Error in worker: {e}")
                            queue.task_done()
                            stop_flag = True
                            break
            
            # Launch workers
            workers = [asyncio.create_task(worker()) for _ in range(max_workers)]
            await queue.join()
            stop_flag = True
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

        async with aiohttp.ClientSession() as session:
            search_queries = self.get_search_queries(matrix_index, matrix_total)
            for query_idx, search_query in enumerate(search_queries):
                if len(repos) >= target_repos:
                    break
                print(f"🔍 Query {query_idx + 1}/{len(search_queries)}: {search_query}")
                await fetch_pages(search_query)
        final_repos = repos[:target_repos]
        unique_owners = len(set(repo['owner'] for repo in final_repos))
        total_stars = sum(repo['stars'] for repo in final_repos)
        avg_stars = total_stars / len(final_repos) if final_repos else 0
        
        print(f"🎉 Crawl completed for matrix job {matrix_index}")
        print(f"📊 Collected: {len(final_repos)} unique repositories")
        print(f"👥 Unique owners: {unique_owners}")
        print(f"⭐ Total stars: {total_stars:,}")
        print(f"📈 Average stars: {avg_stars:.1f}")
        
        # Check for potential overlaps with other matrix jobs
        if len(final_repos) < target_repos:
            print(f"⚠️ Warning: Only collected {len(final_repos)}/{target_repos} repos. Search space may be exhausted for this partition.")
        
        return final_repos
