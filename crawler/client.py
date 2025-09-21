import asyncio
import logging
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
from .state_manager import CrawlerState, StateManager
from .stateful_search_strategy import StatefulSearchStrategy

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

        # Initialize state management if enabled
        self.use_state = settings.crawler_use_stateful_strategy
        if self.use_state:
            self.state_manager = StateManager(
                gist_id=settings.crawler_state_gist_id, github_token=token
            )
            self.stateful_strategy = StatefulSearchStrategy(self.state_manager)
            self.state: CrawlerState | None = None
        else:
            self.state_manager = None
            self.stateful_strategy = None
            self.state = None

        self._connector: aiohttp.TCPConnector | None = None
        self._session: aiohttp.ClientSession | None = None
        logger.info(
            f"✅ GitHub client initialized with token length: {len(token)} (stateful: {self.use_state})"
        )

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

        # Load state if using stateful strategy
        if self.use_state and self.state_manager:
            self.state = await self.state_manager.load_state()
            logger.info(f"Loaded state with {len(self.state.partitions)} partitions")

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        # Save state if using stateful strategy
        if self.use_state and self.state_manager and self.state:
            try:
                gist_id = await self.state_manager.save_state(self.state)
                logger.info(f"Saved state to Gist: {gist_id}")
            except Exception as e:
                logger.error(f"Failed to save state: {e}")

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
    ) -> CrawlResult:
        """
        Main crawling method with optional state management.

        This method:
        - Uses state management to prevent duplicate work when enabled
        - Delegates to appropriate search strategy
        - Implements proper resource management
        - Returns structured results with metadata
        """
        logger.info(
            f"🚀 Starting crawl: Matrix job {matrix_index + 1}/{matrix_total} (stateful: {self.use_state})"
        )
        settings = get_settings()
        if target_repos is None:
            target_repos = settings.crawler_max_repos
        logger.info(f"🎯 Target: {target_repos} repositories")

        # Use stateful crawling if enabled
        if self.use_state and self.stateful_strategy and self.state_manager:
            return await self._crawl_stateful(matrix_total, matrix_index, target_repos)
        else:
            return await self._crawl_standard(matrix_total, matrix_index, target_repos)

    async def _crawl_standard(
        self, matrix_total: int, matrix_index: int, target_repos: int
    ) -> CrawlResult:
        """Standard crawling without state management."""
        repositories: list[Repository] = []
        repository_ids: set[int] = set()

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

    async def _crawl_stateful(
        self, matrix_total: int, matrix_index: int, target_repos: int
    ) -> CrawlResult:
        """Stateful crawling with deduplication and progress tracking."""
        if not self.state:
            self.state = await self.state_manager.load_state()

        # Initialize partitions if needed
        await self.stateful_strategy.initialize_partitions(self.state)

        # Get statistics before crawling
        stats = self.stateful_strategy.get_statistics(self.state)
        logger.info(f"📊 Current progress: {stats['completion_percentage']}% complete")
        logger.info(
            f"📊 Partitions: {stats['pending']} pending, "
            f"{stats['in_progress']} in-progress, "
            f"{stats['completed']} completed"
        )
        logger.info(f"📊 Total unique repositories: {stats['unique_repositories']:,}")

        # Record workflow run
        workflow_run_id = f"{matrix_index}_{matrix_total}_{target_repos}"
        await self.state_manager.record_workflow_run(
            self.state, workflow_run_id, matrix_total, target_repos
        )

        # Get queries for this job
        queries = await self.stateful_strategy.get_queries_for_job(
            self.state, matrix_index, matrix_total, queries_per_job=10
        )

        if not queries:
            logger.warning("⚠️ No queries assigned to this job")
            return CrawlResult(
                repositories=[],
                total_found=0,
                duration_seconds=0.0,
                errors=["No queries available"],
            )

        repositories: list[Repository] = []
        repository_ids: set[int] = set()
        checkpoint_interval = 100

        for query_idx, search_query in enumerate(queries):
            if len(repositories) >= target_repos:
                break

            logger.info(
                f"🔍 Query {query_idx + 1}/{len(queries)}: {search_query.query_string}"
            )

            try:
                # Crawl with deduplication against global state
                query_repos = await self._crawl_query_with_state(
                    search_query, repositories, repository_ids, target_repos
                )

                # Update state
                self.stateful_strategy.mark_query_complete(
                    self.state,
                    search_query.query_string,
                    len(query_repos),
                    exhausted=(len(query_repos) < search_query.expected_results * 0.5),
                )

                # Add to global unique set
                for repo in query_repos:
                    self.state.total_unique_repositories.add(repo.id)

                # Checkpoint periodically
                if (
                    len(repositories) % checkpoint_interval == 0
                    and len(repositories) > 0
                ):
                    logger.info(f"💾 Checkpointing at {len(repositories)} repositories")
                    await self.state_manager.save_state(self.state)

            except Exception as e:
                logger.error(f"❌ Error processing query: {e}")
                continue

        # Final state update
        self.state.total_repositories += len(repositories)

        # Update workflow run info
        if self.state.workflow_runs:
            self.state.workflow_runs[-1]["repositories_collected"] = len(repositories)

        # Save final state
        await self.state_manager.save_state(self.state)

        # Get final statistics
        final_stats = self.stateful_strategy.get_statistics(self.state)
        logger.info(f"🎉 Crawl completed for matrix job {matrix_index}")
        logger.info(f"📊 Collected: {len(repositories)} repositories in this job")
        logger.info(
            f"📊 Global unique repositories: {final_stats['unique_repositories']:,}"
        )
        logger.info(
            f"📊 Overall progress: {final_stats['completion_percentage']}% complete"
        )
        logger.info(
            f"📊 Estimated total repositories: {final_stats['estimated_total_repositories']:,}"
        )

        # Suggest next run configuration
        suggested_matrix = self.stateful_strategy.suggest_matrix_size(self.state)
        logger.info(f"💡 Suggested matrix size for next run: {suggested_matrix}")

        return CrawlResult(
            repositories=repositories[:target_repos],
            total_found=len(repositories),
            duration_seconds=0.0,
            errors=[],
        )

    async def _crawl_query(
        self,
        search_query: SearchQuery,
        repositories: list[Repository],
        repository_ids: set[int],
        target_repos: int,
    ) -> None:
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

    async def _crawl_query_with_state(
        self,
        search_query: SearchQuery,
        repositories: list[Repository],
        repository_ids: set[int],
        target_repos: int,
    ) -> list[Repository]:
        """Crawl a query with state-based deduplication."""
        query_repos = []
        after_cursor = None
        pages_processed = 0
        max_pages = 10

        while len(repositories) < target_repos and pages_processed < max_pages:
            try:
                result = await self.search_repositories(search_query, after_cursor)

                batch_added = 0
                for repo in result["repositories"]:
                    # Check against both local and global state
                    if (
                        repo.id not in repository_ids
                        and repo.id not in self.state.total_unique_repositories
                    ):
                        repositories.append(repo)
                        repository_ids.add(repo.id)
                        query_repos.append(repo)
                        batch_added += 1

                        if len(repositories) >= target_repos:
                            break

                logger.debug(
                    f"📄 Page {pages_processed + 1}: Added {batch_added} new repositories"
                )

                page_info = result["pageInfo"]
                if not page_info["hasNextPage"]:
                    break

                after_cursor = page_info["endCursor"]
                pages_processed += 1

                # Rate limit handling
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

        return query_repos

    async def get_crawling_report(self) -> dict:
        """Generate a comprehensive crawling report."""
        if not self.use_state or not self.state_manager:
            return {
                "error": "State management not enabled",
                "recommendation": "Set USE_STATEFUL_STRATEGY=true and configure CRAWLER_STATE_GIST_ID",
            }

        if not self.state:
            self.state = await self.state_manager.load_state()

        stats = self.stateful_strategy.get_statistics(self.state)

        # Calculate additional metrics
        if stats["completed"] + stats["exhausted"] > 0:
            avg_repos_per_partition = stats["total_repositories"] / (
                stats["completed"] + stats["exhausted"]
            )
        else:
            avg_repos_per_partition = 0

        # Estimate time to completion
        if stats["completion_percentage"] > 0:
            runs_completed = len(self.state.workflow_runs)
            runs_remaining = int(
                runs_completed
                * (100 - stats["completion_percentage"])
                / stats["completion_percentage"]
            )
        else:
            runs_remaining = "Unknown"

        return {
            "summary": {
                "total_unique_repositories": stats["unique_repositories"],
                "total_repositories_seen": stats["total_repositories"],
                "completion_percentage": stats["completion_percentage"],
                "estimated_total": stats["estimated_total_repositories"],
            },
            "partitions": {
                "total": stats["total_partitions"],
                "pending": stats["pending"],
                "in_progress": stats["in_progress"],
                "completed": stats["completed"],
                "exhausted": stats["exhausted"],
            },
            "performance": {
                "workflow_runs": stats["workflow_runs"],
                "avg_repos_per_partition": round(avg_repos_per_partition, 1),
                "estimated_runs_remaining": runs_remaining,
            },
            "recommendations": {
                "next_matrix_size": self.stateful_strategy.suggest_matrix_size(
                    self.state
                ),
                "gist_id": self.state_manager.gist_id,
            },
        }
