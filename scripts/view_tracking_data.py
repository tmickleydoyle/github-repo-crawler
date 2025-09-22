#!/usr/bin/env python3
"""View Supabase repository tracking data."""

import asyncio
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from crawler.tracking_db import RepositoryTracker
from crawler.logger import setup_logging


async def view_tracking_data():
    """View and analyze Supabase tracking data."""

    # Set up logging
    setup_logging()

    print("📊 Supabase Repository Tracking Data")
    print("=" * 50)

    # Check if DATABASE_URL is configured
    if not os.environ.get("DATABASE_URL"):
        print("❌ DATABASE_URL environment variable not set")
        print("Set it with: export DATABASE_URL='your_supabase_connection_string'")
        return

    try:
        async with RepositoryTracker() as tracker:
            # Get comprehensive stats
            stats = await tracker.get_tracking_stats()

            if not stats.get('tracking_enabled'):
                print("❌ Tracking not enabled or connection failed")
                return

            print("📈 Overall Statistics:")
            print(f"  Total Repositories Discovered: {stats['total_discovered']:,}")
            print(f"  Discovered in Last 24 Hours: {stats['discovered_last_24h']:,}")
            print(f"  Discovered in Last Hour: {stats['discovered_last_hour']:,}")
            print(f"  Total Repositories Tracked: {stats['total_tracked']:,}")
            print(f"  Average Stars: {stats['avg_stars']:.1f}")
            print(f"  Maximum Stars: {stats['max_stars']:,}")
            print(f"  Unique Languages: {stats['unique_languages']:,}")

            # Get top repositories
            print(f"\n⭐ Top 10 Repositories by Stars:")
            top_repos = await tracker.get_repository_data(limit=10)

            if top_repos:
                print("   Rank | Repository | Stars | Language | First Seen")
                print("   " + "-" * 65)
                for i, repo in enumerate(top_repos[:10], 1):
                    name = repo['name_with_owner']
                    stars = repo['stars'] or 0
                    language = repo['language'] or 'N/A'
                    first_seen = repo['first_discovered_at']

                    # Format the date
                    if isinstance(first_seen, str):
                        try:
                            first_seen = datetime.fromisoformat(first_seen.replace('Z', '+00:00'))
                        except:
                            pass

                    date_str = first_seen.strftime('%Y-%m-%d') if hasattr(first_seen, 'strftime') else str(first_seen)

                    print(f"   {i:4} | {name[:30]:<30} | {stars:5,} | {language[:10]:<10} | {date_str}")
            else:
                print("   No repositories found")

            # Show recent activity
            print(f"\n🕒 Recent Discovery Activity:")
            recent_repos = await tracker.get_recently_discovered(hours=24)

            if recent_repos:
                print(f"   {len(recent_repos):,} repositories discovered in the last 24 hours")

                # Show sample of recent discoveries
                recent_data = await tracker.get_repository_data(limit=5)
                recent_with_data = [r for r in recent_data if r['id'] in recent_repos]

                if recent_with_data:
                    print("   📋 Recent discoveries with data:")
                    for repo in recent_with_data[:5]:
                        name = repo['name_with_owner']
                        stars = repo['stars'] or 0
                        language = repo['language'] or 'N/A'
                        print(f"     • {name} - {stars:,} stars ({language})")
            else:
                print("   No repositories discovered in the last 24 hours")

            # Deduplication effectiveness
            discovery_rate = (stats['discovered_last_24h'] / stats['total_discovered'] * 100) if stats['total_discovered'] > 0 else 0
            print(f"\n🔄 Deduplication Effectiveness:")
            print(f"   Daily discovery rate: {discovery_rate:.1f}% of total")

            if discovery_rate < 5:
                print("   ✅ Low discovery rate indicates good deduplication")
            elif discovery_rate < 20:
                print("   ⚠️  Moderate discovery rate - some duplicate work")
            else:
                print("   ❌ High discovery rate - may need better deduplication")

            print(f"\n✅ Tracking system is operational and storing data")

    except Exception as e:
        print(f"❌ Error accessing tracking data: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(view_tracking_data())