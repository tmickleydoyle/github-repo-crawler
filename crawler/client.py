import asyncio
import logging
from typing import Any, Dict, List, Optional

import aiohttp
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import settings
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
from .search_strategy import OptimizedSearchStrategy

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

    def __init__(self, token: str = settings.github_token):
        if not token or token == "dummy_token_for_validation":
            raise ValueError("GitHub token is required and must be valid")

        self.graphql_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v4+json",
            "User-Agent": "GitHub-Crawler/1.0",
        }
        self.search_strategy = OptimizedSearchStrategy()
        self._connector = None
        self._session = None
        logger.info(f"✅ GitHub client initialized with token length: {len(token)}")

    async def __aenter__(self):
        """Async context manager entry."""
        self._connector = aiohttp.TCPConnector(
            limit=settings.max_connections,
            limit_per_host=settings.max_connections_per_host,
            keepalive_timeout=30,
            enable_cleanup_closed=True,
        )
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=settings.request_timeout),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
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
    async def _make_graphql_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a GraphQL request with comprehensive retry logic.

        Uses tenacity for robust retry mechanisms with exponential backoff.
        """
        if not self._session:
            raise RuntimeError("Client must be used as async context manager")

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

                    response_data = await resp.json()

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

                        if "data" in response_data and response_data["data"]:
                            logger.warning(
                                f"⚠️ GraphQL errors (continuing): " f"{error_messages}"
                            )
                        else:
                            raise ApiError(f"GraphQL query failed: {error_messages}")

                    return response_data

                resp.raise_for_status()
                return {}
        except aiohttp.ClientError as e:
            logger.warning(f"🔁 Network error: {e}")
            raise

    async def search_repositories(
        self, query: SearchQuery, after: Optional[str] = None
    ) -> Dict[str, Any]:
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
                pushedAt
                updatedAt
                description
                homepageUrl

                # Statistics
                stargazerCount
                forkCount
                watchers {
                  totalCount
                }
                issues(states: OPEN) {
                  totalCount
                }

                # Language information
                primaryLanguage {
                  name
                }
                languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                  nodes {
                    name
                  }
                }

                # Topics
                repositoryTopics(first: 20) {
                  nodes {
                    topic {
                      name
                    }
                  }
                }

                # Owner information
                owner {
                  login
                }

                # License
                licenseInfo {
                  name
                }

                # Repository settings and flags
                defaultBranchRef {
                  name
                }
                visibility
                isPrivate
                isFork
                isArchived
                isDisabled
                isTemplate
                hasIssuesEnabled
                hasProjectsEnabled
                hasWikiEnabled
                hasPages
                hasDownloads

                # Size and network metrics
                diskUsage
                forkingAllowed
                networkCount: forks {
                  totalCount
                }
                subscribers: watchers {
                  totalCount
                }
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

    async def crawl(self, matrix_total: int = 1, matrix_index: int = 0) -> CrawlResult:
        """
        Main crawling method using clean architecture principles.

        This method:
        - Uses domain models instead of raw dictionaries
        - Delegates search strategy to dedicated class
        - Implements proper resource management
        - Returns structured results with metadata
        """
        logger.info(f"🚀 Starting crawl: Matrix job {matrix_index + 1}/{matrix_total}")
        logger.info(f"🎯 Target: {settings.max_repos} repositories")

        repositories: List[Repository] = []
        repository_ids: set[int] = set()
        target_repos = settings.max_repos

        search_queries = self.search_strategy.generate_queries(
            matrix_index, matrix_total
        )

        for query_idx, search_query in enumerate(search_queries):
            if len(repositories) >= target_repos:
                break

            logger.info(
                f"🔍 Query {query_idx + 1}/{len(search_queries)}: "
                f"{search_query.query_string}"
            )

            try:
                await self._crawl_query(
                    search_query, repositories, repository_ids, target_repos
                )
            except SearchExhaustedError:
                logger.warning(
                    f"⚠️ Search exhausted for query: {search_query.query_string}"
                )
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
        else:
            logger.warning("⚠️ No repositories collected")

        if len(final_repositories) < target_repos:
            logger.warning(
                f"⚠️ Only collected {len(final_repositories)}/{target_repos} repos. "
                f"Search space may be exhausted for this partition."
            )

        return crawl_result

    async def _crawl_query(
        self,
        search_query: SearchQuery,
        repositories: List[Repository],
        repository_ids: set,
        target_repos: int,
    ):
        """Process a single search query with pagination."""
        after_cursor = None
        pages_processed = 0
        max_pages = 10

        while len(repositories) < target_repos and pages_processed < max_pages:
            try:
                result = await self.search_repositories(search_query, after_cursor)

                batch_added = 0
                for repo in result["repositories"]:
                    if repo.id not in repository_ids:
                        repositories.append(repo)
                        repository_ids.add(repo.id)
                        batch_added += 1

                        if len(repositories) >= target_repos:
                            break

                logger.debug(
                    f"📄 Page {pages_processed + 1}: "
                    f"Added {batch_added} new repositories"
                )

                page_info = result["pageInfo"]
                if not page_info["hasNextPage"]:
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
