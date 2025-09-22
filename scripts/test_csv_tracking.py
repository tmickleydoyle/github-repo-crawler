#!/usr/bin/env python3
"""Test CSV repository tracking functionality."""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from crawler.csv_tracker import CSVRepositoryTracker


def test_csv_tracking():
    """Test the complete CSV tracking functionality."""

    print("🧪 Testing CSV Repository Tracking")
    print("=" * 50)

    # Use a test CSV file
    test_csv_file = "test_repositories.csv"

    # Clean up any existing test file
    if os.path.exists(test_csv_file):
        os.remove(test_csv_file)
        print("🧹 Cleaned up existing test file")

    try:
        # Test 1: Initialize tracker
        print("\n📊 Initializing CSV tracker...")
        tracker = CSVRepositoryTracker(csv_file_path=test_csv_file)

        # Test 2: Check initial state
        print("\n🔍 Checking initial state...")
        stats = tracker.get_csv_stats()
        print(f"  CSV exists: {stats['csv_exists']}")
        print(f"  Total repositories: {stats['total_repositories']}")

        # Test 3: Get known repository IDs (should be empty)
        known_ids = tracker.get_known_repository_ids()
        print(f"  Known repository IDs: {len(known_ids)}")

        # Test 4: Add some test repositories
        print("\n📝 Adding test repositories...")
        test_repos = [
            {
                'id': 123456789,
                'name': 'test-repo-1',
                'name_with_owner': 'test-user/test-repo-1',
                'url': 'https://github.com/test-user/test-repo-1',
                'created_at': '2025-01-01T00:00:00Z',
                'stars': 100,
                'forks': 20,
                'language': 'Python',
                'owner': 'test-user',
                'license': 'MIT',
                'pushed_at': '2025-01-01T12:00:00Z',
                'updated_at': '2025-01-01T12:00:00Z',
            },
            {
                'id': 987654321,
                'name': 'test-repo-2',
                'name_with_owner': 'test-user/test-repo-2',
                'url': 'https://github.com/test-user/test-repo-2',
                'created_at': '2025-01-02T00:00:00Z',
                'stars': 250,
                'forks': 50,
                'language': 'JavaScript',
                'owner': 'test-user',
                'license': 'Apache-2.0',
                'pushed_at': '2025-01-02T12:00:00Z',
                'updated_at': '2025-01-02T12:00:00Z',
            }
        ]

        run_id = tracker.generate_run_id(10, 0)
        success = tracker.append_repositories_to_csv(test_repos, run_id, 0)

        if success:
            print(f"  ✅ Successfully added {len(test_repos)} repositories")
            print(f"  Run ID: {run_id}")
        else:
            print("  ❌ Failed to add repositories")
            return False

        # Test 5: Check updated state
        print("\n📈 Checking updated state...")
        updated_stats = tracker.get_csv_stats()
        print(f"  CSV exists: {updated_stats['csv_exists']}")
        print(f"  Total repositories: {updated_stats['total_repositories']}")
        print(f"  Unique run IDs: {updated_stats['unique_run_ids']}")
        print(f"  Latest run ID: {updated_stats['latest_run_id']}")

        # Test 6: Check deduplication
        print("\n🔍 Testing deduplication...")
        updated_known_ids = tracker.get_known_repository_ids()
        print(f"  Known repository IDs: {len(updated_known_ids)}")

        for repo in test_repos:
            repo_id = repo['id']
            if tracker.is_repository_known(repo_id):
                print(f"  ✅ Repository {repo_id} is correctly marked as known")
            else:
                print(f"  ❌ Repository {repo_id} should be known but isn't")
                return False

        # Test 7: Test filtering
        print("\n🎯 Testing repository filtering...")
        # Create a mix of new and existing repositories
        mixed_repos = [
            test_repos[0],  # Already exists
            {
                'id': 555666777,
                'name': 'new-repo',
                'name_with_owner': 'test-user/new-repo',
                'url': 'https://github.com/test-user/new-repo',
                'created_at': '2025-01-03T00:00:00Z',
                'stars': 500,
                'forks': 100,
                'language': 'Go',
                'owner': 'test-user',
                'license': 'BSD-3-Clause',
                'pushed_at': '2025-01-03T12:00:00Z',
                'updated_at': '2025-01-03T12:00:00Z',
            }
        ]

        filtered_repos = tracker.filter_new_repositories(mixed_repos)
        print(f"  Input repositories: {len(mixed_repos)}")
        print(f"  Filtered (new) repositories: {len(filtered_repos)}")

        if len(filtered_repos) == 1 and filtered_repos[0]['id'] == 555666777:
            print("  ✅ Filtering worked correctly")
        else:
            print("  ❌ Filtering did not work as expected")
            return False

        # Test 8: Add more repositories from a different run
        print("\n📝 Adding repositories from different matrix job...")
        second_run_id = tracker.generate_run_id(10, 5)
        second_batch = [filtered_repos[0]]  # The new repo from filtering test

        success = tracker.append_repositories_to_csv(second_batch, second_run_id, 5)

        if success:
            print(f"  ✅ Successfully added repositories to second run")
            print(f"  Second run ID: {second_run_id}")
        else:
            print("  ❌ Failed to add repositories to second run")
            return False

        # Test 9: Final verification
        print("\n📋 Final verification...")
        final_stats = tracker.get_csv_stats()
        print(f"  Final total repositories: {final_stats['total_repositories']}")
        print(f"  Final unique run IDs: {final_stats['unique_run_ids']}")

        # Check CSV file contents
        if os.path.exists(test_csv_file):
            with open(test_csv_file, 'r') as f:
                lines = f.readlines()
                print(f"  CSV file has {len(lines)} lines (including header)")
                print(f"  Header: {lines[0].strip()}")

                # Check for run_id column
                if 'run_id' in lines[0]:
                    print("  ✅ Run ID column present in CSV")
                else:
                    print("  ❌ Run ID column missing from CSV")
                    return False

        print("\n✅ All CSV tracking tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up test file
        if os.path.exists(test_csv_file):
            os.remove(test_csv_file)
            print(f"\n🧹 Cleaned up test file: {test_csv_file}")


if __name__ == "__main__":
    success = test_csv_tracking()
    if success:
        print("\n🎉 CSV tracking is working correctly!")
        sys.exit(0)
    else:
        print("\n💥 CSV tracking tests failed!")
        sys.exit(1)