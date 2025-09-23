#!/usr/bin/env python3
"""Analyze existing CSV repository data."""

import csv
import os
import sys
from collections import Counter, defaultdict

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from crawler.csv_tracker import CSVRepositoryTracker


def analyze_csv_data(csv_file_path: str = "github_repositories_final.csv"):
    """Analyze the CSV data to understand current state."""

    print("📊 Analyzing CSV Repository Data")
    print("=" * 50)

    if not os.path.exists(csv_file_path):
        print(f"❌ CSV file not found: {csv_file_path}")
        return

    try:
        # Initialize tracker to get basic stats
        tracker = CSVRepositoryTracker(csv_file_path)
        stats = tracker.get_csv_stats()

        print("📋 Basic Statistics:")
        print(f"  CSV file: {csv_file_path}")
        print(f"  Total repositories: {stats['total_repositories']:,}")
        print(f"  Unique run IDs: {stats['unique_run_ids']}")
        if stats['earliest_run_id']:
            print(f"  Earliest run: {stats['earliest_run_id']}")
        if stats['latest_run_id']:
            print(f"  Latest run: {stats['latest_run_id']}")

        # Detailed analysis
        print("\n🔍 Detailed Analysis:")

        language_count = Counter()
        star_distribution = defaultdict(int)
        run_id_count = Counter()
        matrix_index_count = Counter()
        repo_ids = set()
        total_stars = 0
        repos_with_stars = 0

        with open(csv_file_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            print(f"  CSV headers: {', '.join(headers) if headers else 'None'}")

            has_run_id = 'run_id' in (headers or [])
            has_matrix_index = 'matrix_index' in (headers or [])
            print(f"  Has run_id column: {'✅' if has_run_id else '❌'}")
            print(f"  Has matrix_index column: {'✅' if has_matrix_index else '❌'}")

            for row in reader:
                # Repository ID tracking
                repo_id = None
                for id_col in ['id', 'repo_id', 'databaseId']:
                    if row.get(id_col):
                        try:
                            repo_id = int(row[id_col])
                            break
                        except (ValueError, TypeError):
                            continue

                if repo_id:
                    repo_ids.add(repo_id)

                # Language analysis
                language = row.get('language', '').strip()
                if language and language.lower() != 'null':
                    language_count[language] += 1

                # Star analysis
                stars = row.get('stars', '0')
                try:
                    star_value = int(stars) if stars else 0
                    if star_value > 0:
                        total_stars += star_value
                        repos_with_stars += 1

                    # Star distribution buckets
                    if star_value == 0:
                        star_distribution['0 stars'] += 1
                    elif star_value < 10:
                        star_distribution['1-9 stars'] += 1
                    elif star_value < 100:
                        star_distribution['10-99 stars'] += 1
                    elif star_value < 1000:
                        star_distribution['100-999 stars'] += 1
                    elif star_value < 10000:
                        star_distribution['1K-9K stars'] += 1
                    else:
                        star_distribution['10K+ stars'] += 1

                except (ValueError, TypeError):
                    star_distribution['Unknown'] += 1

                # Run tracking analysis
                if has_run_id and row.get('run_id'):
                    run_id_count[row['run_id']] += 1

                if has_matrix_index and row.get('matrix_index'):
                    try:
                        matrix_idx = int(row['matrix_index'])
                        matrix_index_count[matrix_idx] += 1
                    except (ValueError, TypeError):
                        pass

        print("\n📈 Repository Statistics:")
        print(f"  Unique repository IDs: {len(repo_ids):,}")
        if repos_with_stars > 0:
            avg_stars = total_stars / repos_with_stars
            print(f"  Total stars: {total_stars:,}")
            print(f"  Average stars (repos with stars): {avg_stars:.1f}")
            print(f"  Repositories with stars: {repos_with_stars:,}")

        print("\n🌟 Star Distribution:")
        for bucket, count in sorted(star_distribution.items()):
            percentage = (count / stats['total_repositories'] * 100) if stats['total_repositories'] > 0 else 0
            print(f"  {bucket:<15}: {count:>6,} ({percentage:>5.1f}%)")

        print("\n💻 Top 10 Languages:")
        for lang, count in language_count.most_common(10):
            percentage = (count / stats['total_repositories'] * 100) if stats['total_repositories'] > 0 else 0
            print(f"  {lang:<15}: {count:>6,} ({percentage:>5.1f}%)")

        if run_id_count:
            print("\n🏃 Run Analysis:")
            print(f"  Total runs: {len(run_id_count)}")
            print("  Repositories per run:")
            for run_id, count in sorted(run_id_count.items()):
                print(f"    {run_id}: {count:,} repositories")

        if matrix_index_count:
            print("\n🔢 Matrix Index Distribution:")
            matrix_indices = sorted(matrix_index_count.keys())
            print(f"  Matrix indices used: {len(matrix_indices)} (range: {min(matrix_indices)}-{max(matrix_indices)})")

            # Show distribution
            if len(matrix_indices) <= 20:
                for idx in matrix_indices:
                    count = matrix_index_count[idx]
                    print(f"    Matrix {idx}: {count:,} repositories")
            else:
                print("    (Too many indices to show individually)")

        # Data quality checks
        print("\n🔍 Data Quality:")
        duplicates = stats['total_repositories'] - len(repo_ids)
        if duplicates > 0:
            print(f"  ⚠️  Potential duplicates: {duplicates:,} repositories")
        else:
            print("  ✅ No duplicate repository IDs found")

        if not has_run_id:
            print("  ⚠️  No run_id column - cannot track which run repositories came from")
        else:
            print("  ✅ Run tracking available")

        if not has_matrix_index:
            print("  ⚠️  No matrix_index column - cannot track which matrix job found repositories")
        else:
            print("  ✅ Matrix job tracking available")

        print("\n✅ Analysis complete!")

    except Exception as e:
        print(f"❌ Error analyzing CSV: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "github_repositories_final.csv"
    analyze_csv_data(csv_file)
