#!/usr/bin/env python3
"""Check persistence status and show how it prevents re-crawling."""

import asyncio

from crawler.db_repository import DatabaseRepository


async def main():
    """Show persistence statistics."""
    print("=" * 60)
    print("GitHub Crawler Persistence Status")
    print("=" * 60)

    try:
        async with DatabaseRepository() as db_repo:
            await db_repo.initialize_schema()

            # Get discovery statistics
            stats = await db_repo.get_discovery_stats()

            if stats["total_discovered"] == 0:
                print("\n📭 No repositories discovered yet")
                print("   Run the crawler to start building persistence data")
                return

            print("\n📊 Discovery Statistics:")
            print(f"   • Total repositories discovered: {stats['total_discovered']:,}")
            print(f"   • Discovered in last 24 hours: {stats['discovered_last_24h']:,}")
            print(f"   • Repositories found multiple times: {stats['rediscovered_repos']:,}")
            print(f"   • Matrix jobs used: {stats['matrix_jobs_used']}")

            if stats['first_discovery']:
                print(f"   • First discovery: {stats['first_discovery']}")
            if stats['last_discovery']:
                print(f"   • Last discovery: {stats['last_discovery']}")

            # Calculate persistence effectiveness
            if stats['total_discovered'] > 0:
                rediscovery_rate = (stats['rediscovered_repos'] / stats['total_discovered']) * 100
                recent_rate = (stats['discovered_last_24h'] / stats['total_discovered']) * 100

                print("\n🎯 Persistence Effectiveness:")
                print(f"   • Rediscovery rate: {rediscovery_rate:.1f}%")
                print(f"   • Recent activity: {recent_rate:.1f}%")

                if rediscovery_rate < 10:
                    print("   ✅ Good - Low duplicate discovery rate")
                elif rediscovery_rate < 25:
                    print("   ⚠️  Moderate - Some repositories being rediscovered")
                else:
                    print("   ❌ High - Many repositories being rediscovered (check configuration)")

            print("\n💡 For Hourly GitHub Actions:")
            print("   • Repositories discovered in last 24h will be skipped")
            print("   • Each run will only collect truly new repositories")
            print("   • Database automatically tracks discovery timestamps")
            print("   • Zero wasted API calls on already-crawled repositories")

            if stats['discovered_last_24h'] > 1000:
                print("\n🚀 Ready for Production:")
                print(f"   • {stats['discovered_last_24h']:,} repos discovered recently")
                print("   • Persistence is working effectively")
                print("   • Safe to run hourly without duplicating work")

    except Exception as e:
        print(f"\n❌ Error checking persistence: {e}")
        print("   Make sure the database is running and accessible")


if __name__ == "__main__":
    asyncio.run(main())
