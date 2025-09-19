#!/usr/bin/env python3
"""
🔧 GitHub Actions Pipeline Configuration Helper

This script helps validate and configure the parallel star crawler pipeline.
Run this before using the GitHub Actions workflow to ensure everything is set up correctly.
"""

import json
import os
import sys
from pathlib import Path


def check_requirements():
    """Check if all required files and dependencies are present"""
    print("🔍 Checking pipeline requirements...")

    required_files = [
        "crawler/main.py",
        "crawler/client.py",
        "crawler/config.py",
        "requirements.txt",
        "migrations/001_initial_schema.sql",
        "migrations/002_add_alphabet_partition.sql",
        ".github/workflows/parallel-star-crawler.yml",
        ".github/workflows/code-quality.yml"
    ]

    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)

    if missing_files:
        print("❌ Missing required files:")
        for file in missing_files:
            print(f"   - {file}")
        return False

    print("✅ All required files found")
    return True

def validate_crawler_code():
    """Validate that the crawler supports matrix operations"""
    print("\n🧪 Validating crawler matrix support...")

    try:
        # Test import
        sys.path.append('.')
        from crawler.main import parse_args

        # Check if matrix arguments are supported by reading the source
        main_py_path = Path("crawler/main.py")
        if main_py_path.exists():
            content = main_py_path.read_text()
            if 'matrix_total' in content and 'matrix_index' in content:
                print("✅ Matrix job support detected")
                return True
            else:
                print("❌ Matrix job support not found in main.py")
                return False
        else:
            print("❌ crawler/main.py not found")
            return False

    except ImportError as e:
        print(f"❌ Cannot import crawler module: {e}")
        return False

def calculate_pipeline_estimates():
    """Calculate timing and resource estimates for different configurations"""
    print("\n📊 Pipeline Configuration Estimates (Updated for 5M Scaling):")
    print("===========================================================")

    configurations = [
        {"name": "Test Run", "repos": 5000, "matrix_jobs": 5},
        {"name": "Medium Run", "repos": 50000, "matrix_jobs": 20},
        {"name": "Large Run", "repos": 500000, "matrix_jobs": 50},
        {"name": "Production Run (5M)", "repos": 5000000, "matrix_jobs": 200},
        {"name": "Max Parallel (5M)", "repos": 5000000, "matrix_jobs": 250}
    ]

    for config in configurations:
        repos_per_job = config["repos"] / config["matrix_jobs"]
        # Updated: ~30 queries per job, each potentially yielding 1000 results
        queries_per_job = 30
        api_calls_per_job = queries_per_job * 10  # ~10 API calls per query (pagination)
        # GitHub rate limit is 5000/hour
        estimated_minutes = (api_calls_per_job / 5000) * 60

        print(f"\n🎯 {config['name']}:")
        print(f"   📊 Total Repos: {config['repos']:,}")
        print(f"   ⚡ Matrix Jobs: {config['matrix_jobs']}")
        print(f"   📈 Repos/Job: ~{repos_per_job:.0f}")
        print(f"   🔍 Queries/Job: {queries_per_job}")
        print(f"   ⏱️  Est. Time: ~{estimated_minutes:.1f} minutes per job")
        print(f"   🔥 Parallel Speedup: ~{config['matrix_jobs']}x faster")
        
        if config["repos"] >= 1000000:
            print(f"   🎯 MEGA-SCALE: {config['repos']/1000000:.1f}M repositories!")

def generate_workflow_configs():
    """Generate example workflow configuration files"""
    print("\n📝 Generating workflow configuration examples...")

    configs = {
        "test.json": {
            "target_repos": "5000",
            "matrix_size": "5",
            "description": "Quick test with 5K repos across 5 jobs"
        },
        "medium.json": {
            "target_repos": "50000",
            "matrix_size": "20",
            "description": "Medium run with 50K repos across 20 jobs"
        },
        "large.json": {
            "target_repos": "500000",
            "matrix_size": "50",
            "description": "Large run with 500K repos across 50 jobs"
        },
        "production-5m.json": {
            "target_repos": "5000000",
            "matrix_size": "200",
            "description": "MEGA-SCALE: 5M repositories across 200 jobs"
        },
        "ultra-5m.json": {
            "target_repos": "5000000",
            "matrix_size": "250",
            "description": "ULTRA-SCALE: 5M repositories across 250 jobs for faster completion"
        }
    }

    config_dir = Path("pipeline-configs")
    config_dir.mkdir(exist_ok=True)

    for filename, config in configs.items():
        config_path = config_dir / filename
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✅ Created: {config_path}")

    print("\n💡 Use these configs when triggering the GitHub Actions workflow:")
    print("   Go to Actions → Parallel GitHub Star Crawler → Run workflow")
    print("   Copy values from the JSON files above")

def check_github_token():
    """Check if GitHub token is properly configured"""
    print("\n🔑 GitHub Token Configuration:")

    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("⚠️  GITHUB_TOKEN environment variable not set")
        print("   In GitHub Actions, this will be provided automatically")
        print("   For local testing, set: export GITHUB_TOKEN=your_token_here")
        return False
    else:
        print("✅ GITHUB_TOKEN found in environment")
        print(f"   Token length: {len(token)} characters")
        return True

def main():
    """Main configuration validation"""
    print("🚀 GitHub Actions Parallel Star Crawler Configuration")
    print("=====================================================")

    all_good = True

    # Run all checks
    all_good &= check_requirements()
    all_good &= validate_crawler_code()
    check_github_token()  # Don't fail on this for Actions environment

    calculate_pipeline_estimates()
    generate_workflow_configs()

    print("\n" + "="*60)
    if all_good:
        print("🎉 CONFIGURATION VALIDATION SUCCESSFUL!")
        print("Your pipeline is ready to run in GitHub Actions!")
        print("\n🚀 Next Steps:")
        print("1. Commit and push these files to your GitHub repository")
        print("2. Go to Actions tab in GitHub")
        print("3. Select 'Parallel GitHub Star Crawler' workflow")
        print("4. Click 'Run workflow' and configure your parameters")
        print("5. Watch the magic happen! ✨")
    else:
        print("❌ CONFIGURATION VALIDATION FAILED!")
        print("Please fix the issues above before running the pipeline.")
        sys.exit(1)

if __name__ == "__main__":
    main()
