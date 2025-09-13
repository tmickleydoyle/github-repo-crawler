"""
Memory optimization utilities for the GitHub crawler.

Provides utilities to manage memory usage efficiently when processing
large datasets, particularly useful for high-volume crawling operations.
"""

import gc
import sys
from contextlib import contextmanager
from typing import Any, Callable, Iterator, List, TypeVar

T = TypeVar("T")


def batch_process(items: List[T], batch_size: int = 100) -> Iterator[List[T]]:
    """
    Process items in batches to manage memory usage.

    Args:
        items: List of items to process
        batch_size: Number of items per batch

    Yields:
        Batches of items as lists
    """
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def chunk_list(items: List[T], chunk_size: int) -> Iterator[List[T]]:
    """
    Split a list into chunks of specified size.

    More memory efficient than batch_process for very large lists
    as it doesn't require holding the entire list in memory.
    """
    for i in range(0, len(items), chunk_size):
        chunk = items[i : i + chunk_size]
        yield chunk
        # Clear the chunk reference to help with garbage collection
        del chunk


@contextmanager
def memory_management(force_gc: bool = True, threshold_mb: int = 100):
    """
    Context manager for memory management during data processing.

    Args:
        force_gc: Whether to force garbage collection on exit
        threshold_mb: Memory threshold in MB to warn about
    """
    start_memory = get_memory_usage_mb()

    try:
        yield
    finally:
        if force_gc:
            gc.collect()

        end_memory = get_memory_usage_mb()
        memory_diff = end_memory - start_memory

        if memory_diff > threshold_mb:
            print(f"⚠️ Memory usage increased by {memory_diff:.1f}MB")


def get_memory_usage_mb() -> float:
    """
    Get current memory usage in megabytes.

    Returns:
        Memory usage in MB
    """
    try:
        import psutil

        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        # Fallback to sys.getsizeof estimation
        return sys.getsizeof(gc.get_objects()) / 1024 / 1024


def optimize_list_memory(items: List[Any]) -> List[Any]:
    """
    Optimize memory usage of a list by removing None values and duplicates.

    Args:
        items: List to optimize

    Returns:
        Optimized list with reduced memory footprint
    """
    # Remove None values and convert to set to remove duplicates, then back to list
    return list(set(item for item in items if item is not None))


class MemoryEfficientProcessor:
    """
    A memory-efficient processor for large datasets.

    Processes data in chunks and manages memory automatically.
    """

    def __init__(self, chunk_size: int = 1000, max_memory_mb: int = 512):
        """
        Initialize processor with memory constraints.

        Args:
            chunk_size: Size of processing chunks
            max_memory_mb: Maximum memory to use before forcing cleanup
        """
        self.chunk_size = chunk_size
        self.max_memory_mb = max_memory_mb
        self.processed_count = 0

    def process_repositories(
        self, repositories: List[T], processor_func: Callable[[List[T]], Any]
    ) -> List[Any]:
        """
        Process repositories in memory-efficient chunks.

        Args:
            repositories: List of repositories to process
            processor_func: Function to process each chunk

        Returns:
            List of processing results
        """
        results = []

        with memory_management():
            for chunk in chunk_list(repositories, self.chunk_size):
                # Check memory usage before processing
                current_memory = get_memory_usage_mb()
                if current_memory > self.max_memory_mb:
                    gc.collect()

                try:
                    result = processor_func(chunk)
                    results.append(result)
                    self.processed_count += len(chunk)

                except Exception as e:
                    print(f"⚠️ Error processing chunk: {e}")
                    continue

                # Force cleanup every 10 chunks
                if len(results) % 10 == 0:
                    gc.collect()

        return results

    def get_stats(self) -> dict:
        """Get processing statistics."""
        return {
            "processed_count": self.processed_count,
            "chunk_size": self.chunk_size,
            "max_memory_mb": self.max_memory_mb,
            "current_memory_mb": get_memory_usage_mb(),
        }
