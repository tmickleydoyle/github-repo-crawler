# Debug GitHub Actions Issues

## Check 1: Verify GitHub Secrets

Run these commands to check if secrets are properly set:

```bash
# Check if secrets exist
gh secret list

# Should show:
# DATABASE_URL
# GITHUB_TOKEN
```

## Check 2: Verify GitHub Token Permissions

Your GitHub token needs these permissions:
- [x] **repo** (if accessing private repos)
- [x] **public_repo** (for public repos)
- [x] **read:org** (optional, for better rate limits)

Check in GitHub: Settings → Developer settings → Personal access tokens

## Check 3: Check GitHub Actions Logs

```bash
# View recent workflow runs
gh run list --limit 10

# Get logs for specific run
gh run view [RUN_ID] --log

# Or view in browser
gh run view [RUN_ID] --web
```

## Check 4: Matrix Job Configuration

If you manually changed the matrix to 40 jobs, make sure the indices are correct:

```yaml
matrix:
  matrix_index: [0, 1, 2, ..., 39]  # 40 jobs (0-39)
```

Not:
```yaml
matrix:
  matrix_index: [1, 2, 3, ..., 40]  # Wrong - should start from 0
```

## Check 5: Test Single Job

Create a test workflow with just 1 job to isolate issues:

```yaml
name: Test Single Crawler
on:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - run: pip install -r requirements.txt
    - run: |
        python -m crawler.main --repos 10 --matrix-total 1 --matrix-index 0
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

## Common Failure Patterns

### 1. Authentication Errors
```
Error: GitHub API connection test failed
```
→ Check GITHUB_TOKEN secret and permissions

### 2. Database Connection Errors
```
Error: role "postgres" does not exist
```
→ Check DATABASE_URL secret is properly set

### 3. No Data But Success
```
Crawl completed successfully, repositories_count: 0
```
→ All repos were already discovered (persistence working!)

### 4. Rate Limit Errors
```
Rate limit exceeded
```
→ Too many parallel jobs, reduce matrix size

## Next Steps

1. **Run single test job** to verify basic functionality
2. **Check logs** for specific error messages
3. **Verify secrets** are properly configured
4. **Start with smaller matrix** (5-10 jobs) before scaling to 40-50