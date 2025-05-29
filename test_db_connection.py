#!/usr/bin/env python3
"""
Test script to verify database connection with updated PostgreSQL credentials.
"""

import asyncio
import asyncpg
import os
import sys

# Add the project root to the path
sys.path.insert(0, '.')

async def test_database_connection():
    """Test database connection with the new credentials."""
    
    print("🔍 Testing Database Connection")
    print("=" * 40)
    
    # Test with updated credentials (matching GitHub Actions)
    db_configs = [
        {
            "name": "GitHub Actions Config (postgres/postgres)",
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "postgres",
            "database": "github_crawler"
        },
        {
            "name": "Original Config (crawler_user)",
            "host": "localhost", 
            "port": 5432,
            "user": "crawler_user",
            "password": "crawler_password",
            "database": "github_crawler"
        }
    ]
    
    for config in db_configs:
        print(f"\n🔗 Testing: {config['name']}")
        print(f"   Host: {config['host']}:{config['port']}")
        print(f"   User: {config['user']}")
        print(f"   Database: {config['database']}")
        
        try:
            conn = await asyncpg.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['database']
            )
            
            # Test basic query
            result = await conn.fetchval("SELECT version()")
            print(f"   ✅ Connection successful!")
            print(f"   📋 PostgreSQL version: {result[:50]}...")
            
            # Test table creation
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)
            print(f"   ✅ Table creation successful!")
            
            # Clean up
            await conn.execute("DROP TABLE IF EXISTS test_table")
            await conn.close()
            
        except Exception as e:
            print(f"   ❌ Connection failed: {e}")

async def test_crawler_with_new_db_config():
    """Test running the crawler with the new database configuration."""
    
    print("\n🔍 Testing Crawler with New DB Config")
    print("=" * 45)
    
    # Set environment variables to match GitHub Actions
    os.environ["POSTGRES_HOST"] = "localhost"
    os.environ["POSTGRES_PORT"] = "5432"
    os.environ["POSTGRES_DB"] = "github_crawler"
    os.environ["POSTGRES_USER"] = "postgres"
    os.environ["POSTGRES_PASSWORD"] = "postgres"
    os.environ["MAX_REPOS"] = "10"  # Small number for testing
    
    print(f"Environment variables set:")
    print(f"  POSTGRES_USER: {os.getenv('POSTGRES_USER')}")
    print(f"  POSTGRES_DB: {os.getenv('POSTGRES_DB')}")
    print(f"  MAX_REPOS: {os.getenv('MAX_REPOS')}")
    
    try:
        from crawler.main import run
        
        # Mock sys.argv for testing
        original_argv = sys.argv
        sys.argv = [
            "crawler.main",
            "--repos", "10",
            "--matrix-total", "100",
            "--matrix-index", "0"
        ]
        
        print(f"\n🚀 Running crawler with new DB config...")
        await run()
        print("✅ Crawler completed successfully with new DB config!")
        
    except Exception as e:
        print(f"❌ Crawler failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sys.argv = original_argv

async def main():
    """Main test function."""
    
    print("🚀 Database Connection Test Suite")
    print("🔧 Testing the PostgreSQL credential fix")
    print()
    
    try:
        await test_database_connection()
        await test_crawler_with_new_db_config()
        
        print("\n" + "=" * 50)
        print("✅ Database connection tests completed!")
        print("If all tests passed, the GitHub Actions fix should work.")
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
