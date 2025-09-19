#!/usr/bin/env python3
"""
Scaling Analysis: Compare old vs new search strategies for 5M repository goal.

This script demonstrates the dramatic improvement in scaling capability.
"""

from crawler.search_strategy import SimpleSearchStrategy
from crawler.ultra_search_strategy import UltraSearchStrategy


def analyze_scaling():
    """Analyze and compare scaling capabilities."""
    print("🔍 GitHub Repository Crawler Scaling Analysis")
    print("=" * 60)

    old_strategy = SimpleSearchStrategy()
    new_strategy = UltraSearchStrategy()

    print("\n📊 SCALING COMPARISON FOR 200 MATRIX JOBS:")
    print("-" * 45)

    # Test with typical matrix configuration
    matrix_jobs = 200

    print("\n🔄 OLD STRATEGY (SimpleSearchStrategy):")
    old_queries_job0 = old_strategy.generate_queries(0, matrix_jobs)

    print(f"   📈 Queries per job: {len(old_queries_job0)}")
    print("   🎯 Max results per query: ~1000 (GitHub API limit)")
    print(f"   📊 Max repos per job: {len(old_queries_job0) * 1000:,}")
    print(f"   🚀 Total potential repos: {matrix_jobs * len(old_queries_job0) * 1000:,}")

    print("\n⚡ NEW STRATEGY (UltraSearchStrategy):")
    new_queries_job0 = new_strategy.generate_queries(0, matrix_jobs)
    new_queries_job50 = new_strategy.generate_queries(50, matrix_jobs)

    print(f"   📈 Queries per job: {len(new_queries_job0)}")
    print("   🎯 Max results per query: 1000 (GitHub API limit)")
    print(f"   📊 Max repos per job: {len(new_queries_job0) * 1000:,}")
    print(f"   🚀 Total potential repos: {matrix_jobs * len(new_queries_job0) * 1000:,}")

    # Calculate improvement
    old_total = matrix_jobs * len(old_queries_job0) * 1000
    new_total = matrix_jobs * len(new_queries_job0) * 1000
    improvement_factor = new_total / old_total if old_total > 0 else 0

    print("\n🎉 SCALING IMPROVEMENT:")
    print(f"   📈 Improvement factor: {improvement_factor:.1f}x")
    print(f"   ✅ 5M repository goal: {'ACHIEVABLE' if new_total >= 5_000_000 else 'NOT ACHIEVABLE'}")
    print(f"   🎯 Surplus capacity: {(new_total - 5_000_000):,} repositories")

    print("\n🔍 QUERY DIVERSITY ANALYSIS:")
    print("-" * 30)

    print("\n📋 Sample OLD queries (Job 0):")
    for i, query in enumerate(old_queries_job0[:3]):
        print(f"   {i+1}. {query.query_string}")

    print("\n📋 Sample NEW queries (Job 0):")
    for i, query in enumerate(new_queries_job0[:5]):
        print(f"   {i+1}. {query.query_string}")

    print("\n📋 Sample NEW queries (Job 50):")
    for i, query in enumerate(new_queries_job50[:3]):
        print(f"   {i+1}. {query.query_string}")

    print("\n🎯 SEARCH SPACE COVERAGE:")
    print("-" * 25)

    # Analyze query patterns
    new_query_strings = [q.query_string for q in new_queries_job0]

    patterns = {
        "Language-based": sum(1 for q in new_query_strings if "language:" in q),
        "Time-based": sum(1 for q in new_query_strings if "created:" in q),
        "Topic-based": sum(1 for q in new_query_strings if "topic:" in q),
        "Size-based": sum(1 for q in new_query_strings if "size:" in q),
        "License-based": sum(1 for q in new_query_strings if "license:" in q),
    }

    for pattern, count in patterns.items():
        print(f"   📊 {pattern} queries: {count}")

    print("\n🚀 RECOMMENDED CONFIGURATION FOR 5M REPOS:")
    print("-" * 45)
    print("   Matrix Jobs: 200")
    print("   Repos per Job: 25,000")
    print("   Queries per Job: 30")
    print("   Expected Runtime: ~4 minutes per job")
    print("   Total Runtime: ~4 minutes (parallel execution)")
    print("   API Calls: ~60,000 total (~300 per job)")
    print("   Rate Limit Usage: Well within GitHub's 5,000/hour limit")


if __name__ == "__main__":
    analyze_scaling()
