#!/usr/bin/env python3
"""Calculate how the crawler scales to different repository targets."""

from crawler.search_strategy import SearchStrategy


def main():
    strategy = SearchStrategy()
    stats = strategy.calculate_search_space()

    print("=" * 60)
    print("GitHub Crawler Scale Analysis")
    print("=" * 60)

    print("\n📊 Search Space Breakdown:")
    for query_type, count in stats["breakdown"].items():
        print(f"  • {query_type:20} {count:6,} combinations")

    print(f"\n🔢 Total Combinations: {stats['total_combinations']:,}")
    print(f"📈 Max Theoretical Repos: {stats['max_repos_theoretical']:,}")

    print("\n🎯 Scaling Scenarios:")

    targets = [100_000, 500_000, 1_000_000, 2_500_000, 5_000_000]
    for target in targets:
        # Each query can return ~500 repos on average (not all return 1000)
        avg_repos_per_query = 500
        queries_needed = target // avg_repos_per_query
        jobs_recommended = min(200, max(10, queries_needed // 25))

        print(f"\n  Target: {target:,} repositories")
        print(f"    • Queries needed: ~{queries_needed:,}")
        print(f"    • Matrix jobs recommended: {jobs_recommended}")
        print(f"    • Queries per job: ~{queries_needed // jobs_recommended}")

        if queries_needed > stats["total_combinations"]:
            deficit = queries_needed - stats["total_combinations"]
            print(f"    ⚠️  Need {deficit:,} more query combinations")
            print("        Consider: Adding more granular star ranges or time periods")

    print("\n💡 Current Configuration:")
    print(f"  • Available combinations: {stats['total_combinations']:,}")
    print(f"  • Recommended matrix jobs: {stats['recommended_matrix_jobs']}")

    print("\n📝 Notes:")
    print("  • Each parallel job gets unique, non-overlapping queries")
    print("  • No duplicates between jobs due to deterministic slicing")
    print("  • Queries yielding <100 results are marked as exhausted")
    print("  • Early exit when queries return only duplicates")


if __name__ == "__main__":
    main()
