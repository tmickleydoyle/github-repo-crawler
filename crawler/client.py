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
        """Generate search queries with fine-grained partitions for public repos only"""
        if matrix_total == 1:
            return [
                "is:public stars:0..1 sort:updated",
                "is:public stars:2..5 sort:updated", 
                "is:public stars:6..10 sort:updated",
                "is:public stars:11..25 sort:updated"
            ]
        
        queries = []

        languages = [
            "javascript", "python", "java", "typescript", "go", "rust", "php", "c",
            "c++", "c#", "shell", "ruby", "kotlin", "swift", "scala", "dart",
            "r", "html", "css", "dockerfile", "yaml", "json", "markdown", "tex",
            "powershell", "objective-c", "perl", "haskell", "lua", "vim-script", "none"
        ]
        
        star_buckets = [
            "0", "1", "2..3", "4..5", "6..8", "9..12", "13..18", "19..25",
            "26..35", "36..50", "51..75", "76..100", "101..150", "151..250",
            "251..400", "401..650", "651..1000", "1001..1500", "1501..2500", ">2500"
        ]
        
        date_ranges = [
            "2024-10-01..2025-12-31",
            "2024-07-01..2024-09-30",
            "2024-04-01..2024-06-30",
            "2024-01-01..2024-03-31",
            "2023-10-01..2023-12-31",
            "2023-07-01..2023-09-30",
            "2023-04-01..2023-06-30",
            "2023-01-01..2023-03-31",
            "2022-07-01..2022-12-31",
            "2022-01-01..2022-06-30",
            "2021-01-01..2021-12-31",
            "2020-01-01..2020-12-31",
            "2019-01-01..2019-12-31",
            "..2018-12-31"
        ]
        
        name_ranges = [
            "a..b", "c..d", "e..f", "g..h", "i..j", "k..l", "m..n", "o..p", 
            "q..r", "s..t", "u..v", "w..x", "y..z", "0..4", "5..9", "-"
        ]
        
        total_languages = len(languages)
        total_stars = len(star_buckets)
        total_dates = len(date_ranges)
        total_names = len(name_ranges)
        
        lang_index = matrix_index % total_languages
        star_index = (matrix_index // total_languages) % total_stars
        date_index = (matrix_index // (total_languages * total_stars)) % total_dates
        name_index = (matrix_index // (total_languages * total_stars * total_dates)) % total_names
        
        selected_lang = languages[lang_index]
        selected_stars = star_buckets[star_index]
        selected_date = date_ranges[date_index]
        selected_name = name_ranges[name_index]
        
        base_filters = ["is:public"]
        
        if selected_lang == "none":
            base_filters.append("NOT language:javascript NOT language:python NOT language:java NOT language:typescript NOT language:go")
        else:
            base_filters.append(f"language:{selected_lang}")
        
        if selected_stars == "0":
            base_filters.append("stars:0")
        elif selected_stars == "1":
            base_filters.append("stars:1")
        elif selected_stars.startswith(">"):
            base_filters.append(f"stars:{selected_stars}")
        else:
            base_filters.append(f"stars:{selected_stars}")
        
        if selected_date.startswith(".."):
            base_filters.append(f"created:{selected_date}")
        else:
            base_filters.append(f"created:{selected_date}")
        
        if selected_name == "-":
            base_filters.append("NOT name:a* NOT name:b* NOT name:c* NOT name:d* NOT name:e* NOT name:f* NOT name:g* NOT name:h* NOT name:i* NOT name:j* NOT name:k* NOT name:l* NOT name:m* NOT name:n* NOT name:o* NOT name:p* NOT name:q* NOT name:r* NOT name:s* NOT name:t* NOT name:u* NOT name:v* NOT name:w* NOT name:x* NOT name:y* NOT name:z* NOT name:0* NOT name:1* NOT name:2* NOT name:3* NOT name:4* NOT name:5* NOT name:6* NOT name:7* NOT name:8* NOT name:9*")
        elif ".." in selected_name:
            start, end = selected_name.split("..")
            base_filters.append(f"name:{start}*..{end}*")
        else:
            base_filters.append(f"name:{selected_name}*")
        
        primary_query = " ".join(base_filters) + " sort:updated"
        queries.append(primary_query)
        
        fallback_filters = base_filters[:-1]
        fallback_query = " ".join(fallback_filters) + " sort:stars"
        queries.append(fallback_query)
        
        if len(base_filters) > 3:
            broader_filters = base_filters[:-2]
            broader_query = " ".join(broader_filters) + " sort:updated"
            queries.append(broader_query)
        
        print(f"🎯 Matrix job {matrix_index}: Lang={selected_lang}, Stars={selected_stars}, Date={selected_date}, Name={selected_name}")
        print(f"📊 Generated {len(queries)} fine-grained queries for public repos only")
        
        return queries

    async def crawl(self, matrix_total: int = 1, matrix_index: int = 0) -> List[dict]:
        """Main crawling method - optimized for maximum unique repository collection with parallel page fetching"""
        print(f"🚀 Starting crawl: Matrix job {matrix_index + 1}/{matrix_total}")
        print(f"🎯 Target: {settings.max_repos} repositories")
        
        repos = []
        repo_ids = set()
        target_repos = settings.max_repos
        max_workers = 5
        semaphore = asyncio.Semaphore(max_workers)
        progress_intervals = [0.1, 0.25, 0.5, 0.75, 0.9]
        last_reported = 0

        async def fetch_pages(search_query):
            queue = asyncio.Queue()
            await queue.put(None)
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
                            
                            if batch_added > 0:
                                repos.extend(local_repos[-batch_added:])
                                repo_ids.update(local_ids)
                                local_repos = local_repos[:-batch_added]
                                local_ids.clear()
                                
                            if len(repos) % 100 == 0 and len(repos) > 0:
                                print(f"📊 Collected {len(repos)} unique repositories so far...")
                                
                            current_progress = len(repos) / target_repos
                            for threshold in progress_intervals:
                                if current_progress >= threshold and last_reported < threshold:
                                    print(f"📈 Progress milestone: {threshold*100:.0f}% complete ({len(repos)}/{target_repos} repos)")
                                    last_reported = threshold
                                    break
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
        
        if len(final_repos) < target_repos:
            print(f"⚠️ Warning: Only collected {len(final_repos)}/{target_repos} repos. Search space may be exhausted for this partition.")
        
        return final_repos
