"""
Rate limit aware scheduler for GitHub crawler.

This module helps optimize crawling within GitHub's 5000 GraphQL calls/hour limit.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class RateLimitSchedule:
    """Crawling schedule optimized for rate limits."""

    matrix_size: int
    repos_per_job: int
    estimated_api_calls: int
    can_complete_in_hour: bool
    runs_needed: int
    hours_between_runs: float
    schedule: list[str]


class RateLimitScheduler:
    """Scheduler that optimizes crawling for GitHub's rate limits."""

    # GitHub GraphQL rate limits
    GRAPHQL_CALLS_PER_HOUR = 5000
    CALLS_PER_QUERY = 1  # Each GraphQL query counts as 1 call
    QUERIES_PER_PARTITION = 5  # Average pages needed per partition
    SAFETY_MARGIN = 0.8  # Use only 80% of rate limit for safety

    def calculate_optimal_schedule(
        self,
        total_partitions: int,
        pending_partitions: int,
        target_total_repos: int = 1000000
    ) -> RateLimitSchedule:
        """Calculate optimal crawling schedule based on rate limits."""

        # Calculate effective rate limit
        effective_calls_per_hour = int(self.GRAPHQL_CALLS_PER_HOUR * self.SAFETY_MARGIN)

        # Estimate API calls per partition
        calls_per_partition = self.QUERIES_PER_PARTITION

        # Calculate how many partitions we can process per hour
        partitions_per_hour = effective_calls_per_hour // calls_per_partition

        # Determine optimal matrix size
        if pending_partitions > 5000:
            # Maximum parallelism for large workloads
            matrix_size = 200
            partitions_per_job = max(1, partitions_per_hour // matrix_size)
        elif pending_partitions > 1000:
            # High parallelism
            matrix_size = 100
            partitions_per_job = max(1, partitions_per_hour // matrix_size)
        elif pending_partitions > 200:
            # Medium parallelism
            matrix_size = 50
            partitions_per_job = max(1, partitions_per_hour // matrix_size)
        else:
            # Low parallelism for small workloads
            matrix_size = min(20, pending_partitions)
            partitions_per_job = max(1, pending_partitions // matrix_size)

        # Calculate repos per job (estimate)
        repos_per_partition_avg = 500
        repos_per_job = partitions_per_job * repos_per_partition_avg

        # Calculate total API calls for this configuration
        total_api_calls = matrix_size * partitions_per_job * calls_per_partition

        # Check if we can complete in one hour
        can_complete_in_hour = total_api_calls <= effective_calls_per_hour

        # Calculate runs needed
        if can_complete_in_hour:
            runs_needed = max(1, pending_partitions // (matrix_size * partitions_per_job))
        else:
            # Need multiple runs to stay within rate limit
            partitions_per_run = partitions_per_hour
            runs_needed = max(1, pending_partitions // partitions_per_run)

        # Calculate spacing between runs
        if runs_needed > 1:
            # Need to space out runs to respect rate limit
            hours_between_runs = 1.5  # 90 minutes between runs for safety
        else:
            hours_between_runs = 0

        # Generate schedule
        schedule = self._generate_cron_schedule(runs_needed, hours_between_runs)

        return RateLimitSchedule(
            matrix_size=matrix_size,
            repos_per_job=repos_per_job,
            estimated_api_calls=total_api_calls,
            can_complete_in_hour=can_complete_in_hour,
            runs_needed=runs_needed,
            hours_between_runs=hours_between_runs,
            schedule=schedule
        )

    def _generate_cron_schedule(self, runs_needed: int, hours_between: float) -> list[str]:
        """Generate cron schedule for workflow runs."""
        schedule = []

        if runs_needed <= 1:
            # Single run
            schedule.append("Run once with workflow_dispatch")
        elif runs_needed <= 8:
            # Run throughout the day
            hour_increment = max(3, int(hours_between))
            for i in range(min(runs_needed, 24 // hour_increment)):
                hour = (i * hour_increment) % 24
                schedule.append(f"0 {hour} * * *  # Run {i+1} at {hour:02d}:00")
        else:
            # Need multiple days
            schedule.append("0 */3 * * *  # Every 3 hours")
            schedule.append(f"Estimated completion: {runs_needed // 8} days")

        return schedule

    def estimate_completion_time(
        self,
        pending_partitions: int,
        current_rate: float  # partitions per hour
    ) -> dict:
        """Estimate time to completion based on current crawling rate."""

        if current_rate <= 0:
            return {
                "hours": None,
                "days": None,
                "estimated_completion": "Unknown"
            }

        hours_needed = pending_partitions / current_rate
        days_needed = hours_needed / 24

        completion_date = datetime.now() + timedelta(hours=hours_needed)

        return {
            "hours": round(hours_needed, 1),
            "days": round(days_needed, 1),
            "estimated_completion": completion_date.strftime("%Y-%m-%d %H:%M")
        }

    def suggest_workflow_config(
        self,
        pending_partitions: int,
        avg_repos_per_partition: float = 500
    ) -> dict:
        """Suggest optimal workflow configuration."""

        # Calculate based on rate limits
        effective_calls_per_hour = int(self.GRAPHQL_CALLS_PER_HOUR * self.SAFETY_MARGIN)
        partitions_per_hour = effective_calls_per_hour // self.QUERIES_PER_PARTITION

        # Determine configuration
        if pending_partitions <= partitions_per_hour:
            # Can complete in one run
            matrix_size = min(50, max(1, pending_partitions // 10))
            repos_per_job = (pending_partitions // matrix_size) * int(avg_repos_per_partition)
            frequency = "Once"
        else:
            # Need multiple runs
            matrix_size = 100
            repos_per_job = (partitions_per_hour // matrix_size) * int(avg_repos_per_partition)
            runs_needed = pending_partitions // partitions_per_hour
            frequency = f"Every 90 minutes, {runs_needed} times"

        return {
            "matrix_size": matrix_size,
            "max_repos_per_job": repos_per_job,
            "frequency": frequency,
            "workflow_dispatch_inputs": {
                "matrix_size": str(matrix_size),
                "max_repos_per_job": str(repos_per_job)
            }
        }