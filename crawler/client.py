import asyncio
import logging
import uuid
from typing import Any

import aiohttp
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import get_settings
from .domain import (
    ApiError,
    AuthenticationError,
    CrawlResult,
    RateLimitError,
    Repository,
    SearchExhaustedError,
    SearchQuery,
    transform_github_response,
)
from .search_strategy import SimpleSearchStrategy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GitHubClient:
    """
    GitHub API client with comprehensive retry mechanisms and anti-corruption
    layer.

    This client implements clean architecture principles by:
    - Using domain models instead of raw API responses
    - Implementing proper retry mechanisms with tenacity
    - Providing connection pooling and resource management
    - Isolating external API concerns from business logic
    """

    def __init__(self, token: str | None = None):
        settings = get_settings()
        if token is None:
            token = settings.github_token.get_secret_value()

        if not token or token == "dummy_token_for_validation":
            raise ValueError("GitHub token is required and must be valid")

        # GitHub Actions sets GITHUB_API_URL to https://api.github.com
        # We need the GraphQL endpoint specifically
        if settings.github_api_url == "https://api.github.com":
            self.graphql_url = "https://api.github.com/graphql"
        else:
            self.graphql_url = settings.github_api_url
        logger.info(f"📍 Using GitHub API URL: {self.graphql_url}")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v4+json",
            "User-Agent": "GitHub-Crawler/1.0",
        }
        self.search_strategy = SimpleSearchStrategy()
        self._connector: aiohttp.TCPConnector | None = None
        self._session: aiohttp.ClientSession | None = None
        logger.info(f"✅ GitHub client initialized with token length: {len(token)}")

    async def __aenter__(self) -> "GitHubClient":
        """Async context manager entry."""
        self._connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=20,
            enable_cleanup_closed=True,
            force_close=True,  # Force close connections to avoid reuse issues
            # Note: keepalive_timeout cannot be used with force_close=True
        )
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=30),
            trust_env=True,  # Trust environment proxy settings if any
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._session:
            await self._session.close()
        if self._connector:
            await self._connector.close()

    async def test_connection(self) -> bool:
        """Test GitHub API connection and authentication."""
        test_query = """
        query {
          viewer {
            login
          }
          rateLimit {
            remaining
            resetAt
          }
        }"""

        try:
            response = await self._make_graphql_request({"query": test_query})

            viewer_login = response["data"]["viewer"]["login"]
            rate_limit = response["data"]["rateLimit"]
            logger.info("✅ GitHub API connection successful")
            logger.info(f"📋 Authenticated as: {viewer_login}")
            logger.info(f"🚦 Rate limit remaining: {rate_limit['remaining']}")
            return True
        except Exception as e:
            logger.error(f"❌ GitHub API connection test failed: {e}")
            return False

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((aiohttp.ClientError, RateLimitError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _make_graphql_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Make a GraphQL request with comprehensive retry logic.

        Uses tenacity for robust retry mechanisms with exponential backoff.
        """
        if not self._session:
            raise RuntimeError("Client must be used as async context manager")

        logger.debug(f"🔗 Making GraphQL request to: {self.graphql_url}")
        try:
            async with self._session.post(self.graphql_url, json=payload) as resp:
                if resp.status == 401:
                    raise AuthenticationError("GitHub API authentication failed")

                if resp.status == 403:
                    response_text = await resp.text()
                    if "rate limit" in response_text.lower():
                        logger.warning("⏱️ Rate limit hit, waiting...")
                        await asyncio.sleep(60)
                        raise RateLimitError("GitHub API rate limit exceeded")

                if resp.status in {502, 503, 504}:
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status,
                        message=f"Server error: {resp.status}",
                    )

                if resp.status == 200:
                    remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
                    if remaining < 10:
                        await asyncio.sleep(0.5)

                    response_data: dict[str, Any] = await resp.json()

                    if "errors" in response_data:
                        errors = response_data["errors"]
                        error_messages = [str(error) for error in errors]

                        for error in errors:
                            error_str = str(error)
                            if "FORBIDDEN" in error_str or "Unauthorized" in error_str:
                                raise AuthenticationError(
                                    f"Authentication failed: {error}"
                                )
                            elif "RATE_LIMITED" in error_str:
                                logger.warning("⏱️ GraphQL rate limited, waiting...")
                                await asyncio.sleep(60)
                                raise RateLimitError(f"GraphQL rate limited: {error}")

                        if response_data.get("data"):
                            logger.warning(
                                f"⚠️ GraphQL errors (continuing): {error_messages}"
                            )
                        else:
                            raise ApiError(f"GraphQL query failed: {error_messages}")

                    return response_data

                if resp.status == 404:
                    logger.error(f"❌ 404 Not Found for URL: {self.graphql_url}")
                    logger.error(f"Response headers: {resp.headers}")
                    response_text = await resp.text()
                    logger.error(f"Response body: {response_text[:500]}")
                    raise ApiError(f"GitHub API endpoint not found: {self.graphql_url}")

                resp.raise_for_status()
                return {}
        except aiohttp.ClientError as e:
            logger.warning(f"🔁 Network error: {e}")
            raise

    async def search_repositories(
        self, query: SearchQuery, after: str | None = None
    ) -> dict[str, Any]:
        """
        Execute a GraphQL search query and return repositories using domain models.

        This method implements the anti-corruption layer pattern by:
        - Taking domain SearchQuery objects instead of raw strings
        - Returning structured data with proper typing
        - Handling errors with custom exception types
        """
        graphql_query = """
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
                forkCount
                primaryLanguage {
                  name
                }
                owner {
                  login
                }
                licenseInfo {
                  name
                }
                pushedAt
                updatedAt
              }
            }
          }
          rateLimit {
            remaining
            resetAt
          }
        }"""

        variables = {"searchQuery": query.query_string, "after": after}
        payload = {"query": graphql_query, "variables": variables}

        try:
            response = await self._make_graphql_request(payload)

            if "data" not in response:
                raise ApiError(f"No data in GraphQL response: {response}")

            search_data = response["data"]["search"]
            rate_limit = response["data"]["rateLimit"]

            repositories = []
            for node in search_data["nodes"]:
                repo = transform_github_response(node)
                repositories.append(repo)

            logger.info(f"🔍 Query returned {len(repositories)} repositories")
            logger.info(f"🚦 Rate limit remaining: {rate_limit['remaining']}")

            return {
                "repositories": repositories,
                "pageInfo": search_data["pageInfo"],
                "repositoryCount": search_data["repositoryCount"],
                "rateLimit": rate_limit,
            }

        except (RateLimitError, AuthenticationError, SearchExhaustedError):
            raise
        except Exception as e:
            logger.error(
                f"❌ GraphQL query failed for query '{query.query_string}': {e}"
            )
            raise ApiError(f"Search request failed: {e}") from e

    async def crawl(
        self,
        matrix_total: int = 1,
        matrix_index: int = 0,
        target_repos: int | None = None,
        db_repository=None,
        csv_tracker=None,
    ) -> CrawlResult:
        """
        Main crawling method using clean architecture principles.

        This method:
        - Uses domain models instead of raw dictionaries
        - Delegates search strategy to dedicated class
        - Implements proper resource management
        - Returns structured results with metadata
        """
        logger.info(f"🚀 Starting crawl: Matrix job {matrix_index + 1}/{matrix_total}")
        settings = get_settings()
        if target_repos is None:
            target_repos = settings.crawler_max_repos
        logger.info(f"🎯 Target: {target_repos} repositories")

        repositories: list[Repository] = []
        repository_ids: set[int] = set()
        total_duplicates_found = 0
        exhausted_queries = []
        crawl_run_id = str(uuid.uuid4())[:8]  # Short unique ID for this run

        search_queries = self.search_strategy.generate_queries(
            matrix_index, matrix_total
        )

        logger.info(
            f"📋 Processing {len(search_queries)} unique queries for job {matrix_index}"
        )
        logger.info(f"🆔 Crawl run ID: {crawl_run_id}")

        for query_idx, search_query in enumerate(search_queries):
            if len(repositories) >= target_repos:
                break

            logger.info(
                f"🔍 Query {query_idx + 1}/{len(search_queries)}: "
                f"{search_query.query_string}"
            )

            repos_before = len(repositories)

            try:
                await self._crawl_query(
                    search_query, repositories, repository_ids, target_repos,
                    matrix_index, crawl_run_id, db_repository
                )

                repos_added = len(repositories) - repos_before
                if repos_added < 100:  # Query didn't yield full results
                    exhausted_queries.append(search_query.query_string)

            except SearchExhaustedError:
                logger.warning(
                    f"⚠️ Search exhausted for query: {search_query.query_string}"
                )
                exhausted_queries.append(search_query.query_string)
                continue
            except Exception as e:
                logger.error(
                    f"❌ Error processing query {search_query.query_string}: {e}"
                )
                continue

        final_repositories = repositories[:target_repos]

        crawl_result = CrawlResult(
            repositories=final_repositories,
            total_found=len(repositories),
            duration_seconds=0.0,
            errors=[],
        )

        if final_repositories:
            logger.info(f"🎉 Crawl completed for matrix job {matrix_index}")
            logger.info(f"📊 Collected: {len(final_repositories)} unique repositories")
            logger.info(f"👥 Unique owners: {crawl_result.unique_owners}")
            logger.info(f"⭐ Total stars: {crawl_result.total_stars:,}")
            if crawl_result.total_stars > 0:
                average_stars = crawl_result.total_stars / len(final_repositories)
                logger.info(f"📈 Average stars: {average_stars:.1f}")

            # Report on exhausted queries
            if exhausted_queries:
                logger.info(
                    f"📉 Exhausted queries: {len(exhausted_queries)}/{len(search_queries)} "
                    f"({100 * len(exhausted_queries) / len(search_queries):.1f}%)"
                )
        else:
            logger.warning("⚠️ No repositories collected")

        if len(final_repositories) < target_repos:
            logger.warning(
                f"⚠️ Only collected {len(final_repositories)}/{target_repos} repos. "
                f"Consider increasing matrix_total for better distribution."
            )

        return crawl_result

    async def _crawl_query(
        self,
        search_query: SearchQuery,
        repositories: list[Repository],
        repository_ids: set[int],
        target_repos: int,
        matrix_index: int,
        crawl_run_id: str,
        db_repository=None,
    ) -> None:
        """Process a single search query with pagination, exhaustion tracking, and persistence."""
        after_cursor = None
        pages_processed = 0
        max_pages = 10
        total_for_query = 0
        is_exhausted = False

        while len(repositories) < target_repos and pages_processed < max_pages:
            try:
                result = await self.search_repositories(search_query, after_cursor)

                # Filter repos using persistence if available
                repo_ids_from_page = [repo.id for repo in result["repositories"]]

                # Check against CSV tracking for global deduplication
                known_repo_ids = set()
                if csv_tracker:
                    known_repo_ids = csv_tracker.get_known_repository_ids()
                    logger.debug("CSV tracking loaded",
                               known_repo_count=len(known_repo_ids),
                               csv_file=csv_tracker.csv_file_path)
                else:
                    logger.debug("CSV tracking disabled - using basic deduplication")

                # Only add repos that are NOT already known and not in this run
                batch_added = 0
                new_repos_this_batch = []

                for repo in result["repositories"]:
                    if repo.id not in known_repo_ids and repo.id not in repository_ids:
                        repositories.append(repo)
                        repository_ids.add(repo.id)
                        new_repos_this_batch.append(repo.id)
                        batch_added += 1

                        if len(repositories) >= target_repos:
                            break

                logger.debug("Repository filtering results",
                           page_repos=len(result["repositories"]),
                           known_repos=len(known_repo_ids),
                           already_in_run=len([r for r in result["repositories"] if r.id in repository_ids]),
                           new_repos_added=batch_added)

                # Legacy support for db_repository (PostgreSQL persistence)
                if db_repository and new_repos_this_batch:
                    await db_repository.mark_repositories_discovered(
                        new_repos_this_batch, matrix_index, crawl_run_id
                    )

                total_for_query += len(result["repositories"])

                logger.debug(
                    f"📄 Page {pages_processed + 1}: "
                    f"Added {batch_added} new repositories "
                    f"(Duplicates filtered: {len(result['repositories']) - batch_added})"
                )

                page_info = result["pageInfo"]

                # Check if query is exhausted (no more pages or very few results)
                if not page_info["hasNextPage"]:
                    is_exhausted = True
                    if total_for_query < 100:  # GitHub returns max 100 per page
                        logger.info(
                            f"✅ Query exhausted with {total_for_query} total results: "
                            f"{search_query.query_string}"
                        )
                    break

                # If we're getting too many duplicates, skip to next query
                if batch_added == 0 and pages_processed > 2:
                    logger.warning(
                        f"⚠️ Query yielding only duplicates, moving on: "
                        f"{search_query.query_string}"
                    )
                    break

                after_cursor = page_info["endCursor"]
                pages_processed += 1

                if result["rateLimit"]["remaining"] < 100:
                    logger.info("⏱️ Rate limit low, sleeping...")
                    await asyncio.sleep(1)

            except RateLimitError:
                logger.warning("⏱️ Rate limit hit, sleeping 60 seconds...")
                await asyncio.sleep(60)
                continue
            except Exception as e:
                logger.error(f"❌ Error in query pagination: {e}")
                break
