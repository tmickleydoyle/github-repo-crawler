import aiohttp
import asyncio
import time
import base64
import os
import tempfile
import shutil
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import Optional, List
from .config import settings

class GitHubClient:
    def __init__(self, token: str = settings.github_token):
        self.graphql_url = str(settings.github_api_url)
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v4+json",
            "User-Agent": "GitHub-Crawler/1.0"
        }
        print(f"Initialized GitHub client with token: {token[:10]}...{token[-4:]}")

    @retry(retry=retry_if_exception_type(aiohttp.ClientError),
           wait=wait_exponential(multiplier=1, min=4, max=60),
           stop=stop_after_attempt(5))
    async def _post(self, session: aiohttp.ClientSession, url: str, json: dict):
        async with session.post(url, json=json, headers=self.headers) as resp:
            if resp.status == 403:
                response_text = await resp.text()
                print(f"403 Forbidden Error: {response_text}")
                if "Bad credentials" in response_text:
                    raise Exception("Invalid GitHub token")
                elif "rate limit" in response_text.lower():
                    print("Rate limit exceeded, waiting...")
                    await asyncio.sleep(60)
            resp.raise_for_status()
            return await resp.json()

    async def _rate_limit_pause(self, resp: aiohttp.ClientResponse):
        remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
        reset_ts = int(resp.headers.get("X-RateLimit-Reset", time.time()))
        if remaining < 2:
            sleep_time = max(reset_ts - time.time(), 0) + 1
            print(f"Rate limit pause: {sleep_time}s")
            await asyncio.sleep(sleep_time)

    @retry(retry=retry_if_exception_type((aiohttp.ClientError, aiohttp.ClientResponseError)),
           wait=wait_exponential(multiplier=2, min=4, max=120),
           stop=stop_after_attempt(3))
    async def _get(self, session: aiohttp.ClientSession, url: str) -> dict:
        async with session.get(url, headers=self.headers) as resp:
            if resp.status == 403:
                if 'rate limit' in resp.reason.lower() or 'api rate limit' in (await resp.text()).lower():
                    print(f"Rate limit hit, waiting...")
                    await asyncio.sleep(60)
                    raise aiohttp.ClientResponseError(resp.request_info, resp.history, status=resp.status)
            resp.raise_for_status()
            await self._rate_limit_pause(resp)
            return await resp.json()

    async def fetch_repos(self, session: aiohttp.ClientSession, after: Optional[str], alphabet_filter: Optional[str] = None):
        base_query = "stars:>0"
        if alphabet_filter:
            if '-' in alphabet_filter and len(alphabet_filter) == 3:
                start, end = alphabet_filter.split('-')
                owner_queries = []
                for char in "abcdefghijklmnopqrstuvwxyz":
                    if start <= char <= end:
                        owner_queries.append(f"user:{char}*")
                if owner_queries:
                    query = f"{base_query} " + " OR ".join(owner_queries)
                else:
                    query = base_query
            else:
                owner_queries = [f"user:{char}*" for char in alphabet_filter.lower()]
                query = f"{base_query} " + " OR ".join(owner_queries)
        else:
            query = base_query
            
        graphql_query = f'''
        query ($after: String) {{
          search(query: "{query}", type: REPOSITORY, first: {settings.batch_size}, after: $after) {{
            pageInfo {{ endCursor hasNextPage }}
            nodes {{
              ... on Repository {{
                databaseId
                name
                url
                createdAt
                stargazerCount
                owner {{ login }}
              }}
            }}
          }}
        }}'''
        payload = {"query": graphql_query, "variables": {"after": after}}
        data = await self._post(session, self.graphql_url, payload)
        return data["data"]["search"]

    async def crawl(self, alphabet_filter: Optional[str] = None) -> List[dict]:
        repos = []
        after = None
        batch_count = 0
        
        if alphabet_filter:
            print(f"🔤 Using alphabetical filter: {alphabet_filter}")
        
        async with aiohttp.ClientSession() as session:
            while len(repos) < settings.max_repos:
                try:
                    batch_count += 1
                    print(f"Fetching batch {batch_count}, current repos: {len(repos)}/{settings.max_repos}")
                    
                    search = await self.fetch_repos(session, after, alphabet_filter)
                    batch_repos = []
                    
                    for node in search["nodes"]:
                        batch_repos.append({
                            "id": node["databaseId"],
                            "name": node["name"],
                            "owner": node["owner"]["login"],
                            "url": node["url"],
                            "created_at": node["createdAt"],
                            "stars": node["stargazerCount"]
                        })
                    
                    repos.extend(batch_repos)
                    print(f"Added {len(batch_repos)} repositories, total: {len(repos)}")
                    
                    if not search["pageInfo"]["hasNextPage"]:
                        print("No more pages available")
                        break
                        
                    after = search["pageInfo"]["endCursor"]
                    
                    if len(repos) < settings.max_repos:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    print(f"Error in batch {batch_count}: {e}")
                    if repos:
                        print(f"Continuing with {len(repos)} repositories collected so far")
                        break
                    else:
                        raise
                        
        final_repos = repos[:settings.max_repos]
        print(f"Crawl completed: {len(final_repos)} repositories collected")
        return final_repos

    async def fetch_repo_file_tree(self, session: aiohttp.ClientSession, owner: str, name: str, branch: str = "main"):
        url = f"https://api.github.com/repos/{owner}/{name}/git/trees/{branch}?recursive=1"
        data = await self._get(session, url)
        return [n for n in data.get("tree", []) if n["type"] == "blob"]

    async def fetch_blob(self, session: aiohttp.ClientSession, owner: str, name: str, sha: str) -> str:
        url = f"https://api.github.com/repos/{owner}/{name}/git/blobs/{sha}"
        data = await self._get(session, url)
        raw = data.get("content", "")
        
        try:
            if data.get("encoding") == "base64":
                decoded = base64.b64decode(raw)
                try:
                    return decoded.decode("utf-8")
                except UnicodeDecodeError:
                    return f"[BINARY_BASE64]{raw}"
            else:
                return raw
        except Exception as e:
            return f"[ERROR_DECODING]{str(e)}"

    async def crawl_files_for_repo(self, session: aiohttp.ClientSession, repo: dict) -> List[dict]:
        owner, name, rid = repo["owner"], repo["name"], repo["id"]
        files = []
        try:
            tree = await self.fetch_repo_file_tree(session, owner, name)
            
            filtered_tree = []
            for node in tree:
                if node["type"] == "blob":
                    file_size = node.get("size", 0)
                    if file_size <= 10 * 1024 * 1024:
                        filtered_tree.append(node)
                    else:
                        print(f"Skipping large file {node['path']} ({file_size} bytes)")
            
            print(f"Fetching {len(filtered_tree)} files for {owner}/{name}...")
            
            max_concurrent = min(15, max(5, len(filtered_tree) // 10))
            sem = asyncio.Semaphore(max_concurrent)
            
            async def fetch_blob(node):
                async with sem:
                    try:
                        content = await self.fetch_blob(session, owner, name, node["sha"])
                        files.append({
                            "path": node["path"], 
                            "content": content,
                            "sha": node["sha"],
                            "size": node.get("size", 0)
                        })
                    except Exception as e:
                        print(f"Failed to fetch {node['path']}: {e}")
                        files.append({
                            "path": node["path"], 
                            "content": f"ERROR: {str(e)}",
                            "sha": node["sha"],
                            "size": node.get("size", 0),
                            "error": True
                        })
            
            if filtered_tree:
                batch_size = 50
                for i in range(0, len(filtered_tree), batch_size):
                    batch = filtered_tree[i:i + batch_size]
                    print(f"Processing batch {i//batch_size + 1}/{(len(filtered_tree) + batch_size - 1)//batch_size} ({len(batch)} files)")
                    await asyncio.gather(*(fetch_blob(n) for n in batch), return_exceptions=True)
                    
                    if i + batch_size < len(filtered_tree):
                        await asyncio.sleep(1)
                
        except Exception as e:
            print(f"[WARN] failed to fetch files for {owner}/{name}: {e}")
        
        print(f"Successfully fetched {len([f for f in files if not f.get('error')])} files for {owner}/{name}")
        return files

    async def clone_repo_with_git(self, repo: dict, temp_dir: str) -> List[dict]:
        """Clone repository using git and extract all files"""
        owner, name = repo["owner"], repo["name"]
        clone_url = f"https://github.com/{owner}/{name}.git"
        repo_path = os.path.join(temp_dir, f"{owner}-{name}")
        
        try:
            clone_cmd = [
                "git", "clone", 
                "--depth", "1", 
                "--single-branch",
                "--no-tags",
                clone_url, 
                repo_path
            ]
            
            print(f"Cloning {owner}/{name}...")
            process = await asyncio.create_subprocess_exec(
                *clone_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_dir
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=300
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                print(f"Git clone timeout for {owner}/{name}")
                return []
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                print(f"Git clone failed for {owner}/{name}: {error_msg}")
                return []
            
            files = []
            repo_pathlib = Path(repo_path)
            
            for file_path in repo_pathlib.rglob("*"):
                if file_path.is_file() and not self._should_skip_file(file_path):
                    try:
                        relative_path = file_path.relative_to(repo_pathlib)
                        file_size = file_path.stat().st_size
                        
                        try:
                            content = file_path.read_text(encoding='utf-8', errors='ignore')
                            files.append({
                                "path": str(relative_path),
                                "content": content,
                                "size": file_size
                            })
                        except Exception:
                            files.append({
                                "path": str(relative_path),
                                "content": "[BINARY_FILE]",
                                "size": file_size
                            })
                            
                    except Exception as e:
                        print(f"Error reading file {file_path}: {e}")
                        continue
            
            print(f"Successfully cloned {owner}/{name} - extracted {len(files)} files")
            return files
            
        except Exception as e:
            print(f"Error cloning {owner}/{name}: {e}")
            return []
        finally:
            if os.path.exists(repo_path):
                shutil.rmtree(repo_path, ignore_errors=True)

    def _should_skip_file(self, file_path: Path) -> bool:
        """Determine if a file should be skipped during extraction"""
        parts = file_path.parts
        
        if '.git' in parts:
            return True
            
        skip_dirs = {
            'node_modules', '__pycache__', '.pytest_cache', 'venv', 'env', '.env',
            'build', 'dist', 'target', 'bin', 'obj', '.idea', '.vscode',
            'coverage', '.nyc_output', 'logs', 'tmp', 'temp', '.cache',
            '.gradle', '.maven', 'vendor', 'bower_components'
        }
        
        if any(part in skip_dirs for part in parts):
            return True
        
        file_name = file_path.name.lower()
        file_suffix = file_path.suffix.lower()
        
        skip_patterns = {
            '.pyc', '.pyo', '.class', '.o', '.obj', '.dll', '.so', '.dylib',
            '.zip', '.tar', '.gz', '.rar', '.7z', '.jar', '.war', '.ear',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico', '.webp',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.mp3', '.mp4', '.avi', '.mov', '.wav', '.flv', '.wmv',
            '.db', '.sqlite', '.sqlite3', '.mdb',
            '.log', '.out',
            '.iml', '.ipr', '.iws',
        }
        
        if file_suffix in skip_patterns:
            return True
            
        if file_name.startswith('.') and file_suffix not in {'.env', '.gitignore', '.gitattributes', '.editorconfig'}:
            return True
            
        try:
            if file_path.stat().st_size > 5 * 1024 * 1024:
                return True
        except:
            pass
            
        return False

    async def crawl_files_for_repo_with_git(self, repo: dict, temp_dir: str) -> List[dict]:
        """New method that uses git clone instead of API calls"""
        return await self.clone_repo_with_git(repo, temp_dir)

    async def skip_to_partition(self, session: aiohttp.ClientSession, target_skip: int, alphabet_filter: Optional[str] = None) -> Optional[str]:
        """Skip to the correct partition starting point by iterating through pages"""
        if target_skip <= 0:
            return None
            
        print(f"🔍 Seeking to partition starting point (skipping {target_skip} repositories)...")
        skipped = 0
        after = None
        
        while skipped < target_skip:
            search = await self.fetch_repos(session, after, alphabet_filter)
            batch_size = len(search["nodes"])
            
            if skipped + batch_size <= target_skip:
                skipped += batch_size
                print(f"⏭️  Skipped batch: {batch_size} repos (total skipped: {skipped})")
            else:
                remaining_skip = target_skip - skipped
                print(f"🎯 Found starting partition at offset {remaining_skip} in current batch")
                return after
                
            if not search["pageInfo"]["hasNextPage"]:
                print("⚠️  Reached end of results while seeking partition")
                return None
                
            after = search["pageInfo"]["endCursor"]
            
            await asyncio.sleep(0.2)
        
        print(f"✅ Successfully skipped to partition starting point")
        return after
