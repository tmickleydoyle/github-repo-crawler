#!/bin/bash

# CI Simulation Script for GitHub Actions
# This script replicates the environment and checks that would run in CI

set -e  # Exit on any error

echo "🚀 Starting CI Simulation..."
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2 PASSED${NC}"
    else
        echo -e "${RED}❌ $2 FAILED${NC}"
        exit 1
    fi
}

echo "📦 Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt
print_status $? "Dependency Installation"

echo ""
echo "🔍 Running Code Quality Checks..."
echo "--------------------------------"

# 1. Linting with flake8
echo "1️⃣ Running flake8 linting..."
python -m flake8 crawler/ tests/ --count --statistics
print_status $? "Flake8 Linting"

# 2. Type checking with mypy
echo "2️⃣ Running mypy type checking..."
python -m mypy crawler/ tests/ --ignore-missing-imports
print_status $? "MyPy Type Checking"

# 3. Code formatting check with black
echo "3️⃣ Checking code formatting..."
python -m black --check crawler/ tests/ --line-length 88
print_status $? "Black Code Formatting"

# 4. Import validation
echo "4️⃣ Validating module imports..."
python -c "
import sys
sys.path.append('.')

try:
    from crawler import client, main, config, domain, search_strategy
    print('✅ All core modules import successfully')
except Exception as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)

try:
    from crawler.config import settings
    print('✅ Configuration loads successfully')
except Exception as e:
    print(f'❌ Config error: {e}')
    sys.exit(1)
"
print_status $? "Module Import Validation"

# 5. Run tests
echo "5️⃣ Running test suite..."
python -m pytest tests/ -v --tb=short
print_status $? "Test Suite"

# 6. Test coverage check (informational)
echo "6️⃣ Checking test coverage..."
python -m pytest tests/ --cov=crawler --cov-report=term-missing --quiet
COVERAGE_EXIT=$?
if [ $COVERAGE_EXIT -eq 0 ]; then
    echo -e "${GREEN}✅ Coverage check completed${NC}"
else
    echo -e "${YELLOW}⚠️ Coverage below threshold (acceptable for this task)${NC}"
fi

echo ""
echo "🎉 CI Simulation Results:"
echo "========================="
echo -e "${GREEN}✅ All critical quality checks passed!${NC}"
echo -e "${GREEN}✅ Code is ready for GitHub Actions${NC}"
echo ""
echo "📊 Summary:"
echo "- Linting: 0 issues"
echo "- Type Safety: Clean"
echo "- Code Style: Consistent"
echo "- Tests: All passing"
echo "- Imports: Valid"
echo ""
echo "🚀 Ready for deployment!"
