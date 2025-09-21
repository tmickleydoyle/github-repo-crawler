"""
Stateful search strategy that tracks progress and prevents duplicate work.

This strategy integrates with the state manager to ensure systematic coverage
of the GitHub repository space without overlap across workflow runs.
"""

import logging

from .domain import SearchQuery
from .search_space import SearchSpaceGenerator
from .state_manager import CrawlerState, SearchSpacePartition, StateManager

logger = logging.getLogger(__name__)


class StatefulSearchStrategy:
    """Search strategy that maintains state across workflow runs."""

    def __init__(self, state_manager: StateManager):
        """Initialize with a state manager."""
        self.state_manager = state_manager
        self.space_generator = SearchSpaceGenerator()

    async def initialize_partitions(
        self, state: CrawlerState, max_partitions: int = 10000
    ) -> None:
        """Initialize search partitions if not already present."""
        if not state.partitions:
            logger.info(f"Initializing search partitions (max: {max_partitions})")

            # Generate priority partitions first
            priority_partitions = self.space_generator.generate_priority_partitions(
                count=min(5000, max_partitions)
            )

            for partition in priority_partitions:
                state.partitions[partition.partition_id] = SearchSpacePartition(
                    partition_id=partition.partition_id,
                    query=partition.query,
                    status="pending",
                    repositories_found=0,
                )

            # Add more diverse partitions if room
            if len(state.partitions) < max_partitions:
                remaining = max_partitions - len(state.partitions)
                for i, partition in enumerate(
                    self.space_generator.generate_all_partitions()
                ):
                    if i >= remaining:
                        break
                    if partition.partition_id not in state.partitions:
                        state.partitions[partition.partition_id] = SearchSpacePartition(
                            partition_id=partition.partition_id,
                            query=partition.query,
                            status="pending",
                            repositories_found=0,
                        )

            logger.info(f"Initialized {len(state.partitions)} search partitions")
            await self.state_manager.save_state(state)

    async def get_queries_for_job(
        self,
        state: CrawlerState,
        matrix_index: int,
        matrix_total: int,
        queries_per_job: int = 5,
    ) -> list[SearchQuery]:
        """Get search queries for a specific matrix job."""
        queries = []

        # Ensure partitions are initialized
        if not state.partitions:
            await self.initialize_partitions(state)

        # Get pending and in-progress partitions
        pending_partitions = [
            p for p in state.partitions.values() if p.status == "pending"
        ]

        in_progress_partitions = [
            p for p in state.partitions.values() if p.status == "in_progress"
        ]

        # Retry in-progress partitions (might have failed)
        retryable = in_progress_partitions[: queries_per_job // 2]
        for partition in retryable:
            queries.append(
                SearchQuery(
                    query_string=partition.query,
                    description=f"Retry: {partition.partition_id}",
                    expected_results=500,
                )
            )
            partition.error_count += 1

        # Assign new pending partitions
        remaining_slots = queries_per_job - len(queries)

        # Deterministic assignment based on matrix index
        if pending_partitions:
            # Each job gets a slice of pending partitions
            partitions_per_job = max(1, len(pending_partitions) // matrix_total)
            start_idx = matrix_index * partitions_per_job
            end_idx = min(start_idx + remaining_slots, len(pending_partitions))

            assigned_partitions = pending_partitions[start_idx:end_idx]

            for partition in assigned_partitions:
                queries.append(
                    SearchQuery(
                        query_string=partition.query,
                        description=f"Partition: {partition.partition_id}",
                        expected_results=500,
                    )
                )
                # Mark as in-progress
                partition.status = "in_progress"
                partition.started_at = partition.started_at or state.last_updated

        # If no queries assigned, try to find any available work
        if not queries and pending_partitions:
            for partition in pending_partitions[:queries_per_job]:
                queries.append(
                    SearchQuery(
                        query_string=partition.query,
                        description=f"Fallback: {partition.partition_id}",
                        expected_results=500,
                    )
                )
                partition.status = "in_progress"
                partition.started_at = state.last_updated

        logger.info(
            f"Job {matrix_index + 1}/{matrix_total}: Assigned {len(queries)} queries "
            f"({len(pending_partitions)} pending, {len(in_progress_partitions)} in-progress)"
        )

        return queries

    def mark_query_complete(
        self,
        state: CrawlerState,
        query: str,
        repositories_found: int,
        exhausted: bool = False,
    ) -> None:
        """Mark a query/partition as complete."""
        # Find partition by query
        partition_id = None
        for pid, partition in state.partitions.items():
            if partition.query == query:
                partition_id = pid
                break

        if partition_id:
            self.state_manager.mark_partition_complete(
                state, partition_id, repositories_found, exhausted
            )
        else:
            logger.warning(f"Could not find partition for query: {query}")

    def get_statistics(self, state: CrawlerState) -> dict:
        """Get crawling statistics from state."""
        total_partitions = len(state.partitions)
        pending = sum(1 for p in state.partitions.values() if p.status == "pending")
        in_progress = sum(
            1 for p in state.partitions.values() if p.status == "in_progress"
        )
        completed = sum(1 for p in state.partitions.values() if p.status == "completed")
        exhausted = sum(1 for p in state.partitions.values() if p.status == "exhausted")

        total_repos = sum(p.repositories_found for p in state.partitions.values())

        # Estimate completion
        processed = completed + exhausted
        completion_pct = (
            (processed / total_partitions * 100) if total_partitions > 0 else 0
        )

        # Estimate total repositories (based on average)
        if processed > 0:
            avg_per_partition = total_repos / processed
            estimated_total = int(avg_per_partition * total_partitions)
        else:
            estimated_total = total_partitions * 500  # Rough estimate

        return {
            "total_partitions": total_partitions,
            "pending": pending,
            "in_progress": in_progress,
            "completed": completed,
            "exhausted": exhausted,
            "total_repositories": total_repos,
            "unique_repositories": len(state.total_unique_repositories),
            "completion_percentage": round(completion_pct, 2),
            "estimated_total_repositories": estimated_total,
            "workflow_runs": len(state.workflow_runs),
        }

    def suggest_matrix_size(self, state: CrawlerState) -> int:
        """Suggest optimal matrix size based on remaining work."""
        pending = sum(1 for p in state.partitions.values() if p.status == "pending")

        # GitHub Actions allows up to 256 matrix jobs
        if pending > 5000:
            return 200  # Max practical size
        elif pending > 2000:
            return 100
        elif pending > 500:
            return 50
        elif pending > 100:
            return 20
        else:
            return max(1, min(10, pending))
