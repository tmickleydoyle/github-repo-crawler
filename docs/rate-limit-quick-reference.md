# Rate Limit Graceful Shutdown - Quick Reference

## What It Does

When a GitHub Actions matrix runner starts with an **already exhausted** API rate limit, the crawler will:
1. ✅ Detect the error automatically
2. ✅ Save any repositories collected before hitting the limit
3. ✅ Exit with success code (0) instead of failure
4. ✅ Allow the GitHub Actions job to complete successfully

## How to Identify

### Log Messages

Look for these log messages indicating graceful shutdown:

```
ERROR:crawler.client:🛑 API rate limit already exhausted
INFO:crawler.client:💾 Saving 247 repositories collected before rate limit
WARNING:crawler.main:Rate limit exhausted - saving partial results
WARNING:crawler.main:Crawler stopped gracefully due to API rate limit exhaustion
```

### GitHub Actions Output

```
✅ Job completed with exit code 0
```

## Error Detection

The system detects this specific error pattern from GitHub's GraphQL API:

```json
{
  "errors": [{
    "type": "RATE_LIMIT",
    "message": "API rate limit already exceeded for site ID installation."
  }]
}
```

**Key difference from regular rate limits:**
- Regular: "rate limit exceeded" → retry after 60s
- Exhausted: "already exceeded" → stop gracefully

## Code Locations

### Exception Definition
`crawler/domain.py:87-90`

### Detection Logic
`crawler/client.py:164-178`

### Crawl Loop Handler
`crawler/client.py:347-365`

### Exit Code Handler
`crawler/main.py:100-106`

## Testing

Run the specific test:
```bash
pytest tests/test_client.py::TestGitHubClientRequestHandling::test_graphql_request_rate_limit_exhausted -v
```

Run all tests:
```bash
pytest tests/ -v
```

## Expected Behavior

### Scenario 1: Rate Limit Hit During Crawling
```
Start crawling → Collect 500 repos → Hit rate limit
→ Wait 60s → Continue crawling → Collect more repos
```

### Scenario 2: Rate Limit Already Exhausted (NEW)
```
Start crawling → Collect 50 repos → Detect exhausted limit
→ Save 50 repos → Exit with code 0 ✅
```

## Configuration

**No configuration required** - the feature is automatic.

## Troubleshooting

### Job Still Failing?

Check if the error message contains "already exceeded":
- ✅ Has "already exceeded" → graceful shutdown should work
- ❌ No "already exceeded" → different error type

### Partial Results Not Saved?

Check that these complete successfully:
1. Database write: `await db_repo.store_repositories()`
2. CSV export: `csv_deduplicator.export_repositories_to_csv()`

Both should complete before the exit.

### GitHub Actions Job Marked as Failed?

The exit code should be 0. Check the workflow logs for:
```
exit code: 0
```

If exit code is non-zero, the RateLimitExhaustedError may not be caught properly.

## Related Documentation

- [Full Documentation](./graceful-shutdown-on-rate-limit.md)
- [Flow Diagram](./rate-limit-flow.md)
- [GitHub GraphQL Rate Limits](https://docs.github.com/en/graphql/overview/resource-limitations)

## Support

If you encounter issues:
1. Check the test suite passes: `pytest tests/`
2. Review the log messages for the specific error
3. Verify the error message contains "already exceeded"
4. Check the GitHub Actions workflow output for exit codes

