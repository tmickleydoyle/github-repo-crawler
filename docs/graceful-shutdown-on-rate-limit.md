# Graceful Shutdown on API Rate Limit Exhaustion

## Overview

When running the GitHub crawler in a matrix of parallel jobs, some runners may encounter an already-exhausted API rate limit. This feature implements graceful shutdown handling to ensure partial results are saved and GitHub Actions jobs exit cleanly without failing.

## Problem Statement

When GitHub Actions runners start with an exhausted API rate limit, the crawler would previously:
- Log errors but continue attempting to crawl
- Not save partial results before stopping
- Exit with an error code, marking the job as failed
- Create noise in the logs and make debugging harder

Example error message:
```
ERROR:crawler.client:❌ Error in query pagination: Search request failed: GraphQL query failed: ["{'type': 'RATE_LIMIT', 'code': 'graphql_rate_limit', 'message': 'API rate limit already exceeded for site ID installation.'}"]
```

## Solution

The implementation adds graceful shutdown logic with the following components:

### 1. New Exception Type

**File:** `crawler/domain.py`

```python
class RateLimitExhaustedError(ApiError):
    """Exception raised when API rate limit is already exhausted before crawl starts."""
    pass
```

This exception specifically identifies pre-exhausted rate limits (different from hitting the limit during crawling).

### 2. Detection in GraphQL Request Handler

**File:** `crawler/client.py:164-178`

The `_make_graphql_request` method now detects rate limit exhaustion:

```python
if "RATE_LIMITED" in error_str or "RATE_LIMIT" in error_str:
    if "already exceeded" in error_str.lower():
        logger.error("🛑 API rate limit already exhausted")
        raise RateLimitExhaustedError(
            f"API rate limit already exhausted: {error}"
        )
```

**Detection criteria:**
- Response contains `RATE_LIMIT` or `RATE_LIMITED` in error type
- Error message contains "already exceeded" text

### 3. Graceful Stop in Crawl Loop

**File:** `crawler/client.py:347-353`

The main crawl loop catches the exception and stops gracefully:

```python
except RateLimitExhaustedError as e:
    logger.error(
        f"🛑 API rate limit exhausted - gracefully stopping crawler: {e}"
    )
    logger.info(
        f"💾 Saving {len(repositories)} repositories collected before rate limit"
    )
    break
```

**Behavior:**
- Logs clear message about rate limit exhaustion
- Reports how many repositories were collected before the limit
- Breaks the crawl loop (does NOT raise the exception)
- Allows cleanup and data persistence to proceed

### 4. Graceful Stop in Query Pagination

**File:** `crawler/client.py:507-509`

The pagination loop re-raises the exception to stop further queries:

```python
except RateLimitExhaustedError:
    logger.error("🛑 API rate limit already exhausted - stopping pagination")
    raise
```

### 5. Clean Exit from Main Entry Point

**File:** `crawler/main.py`

Multiple layers handle the exception:

**Top-level handler (main.py:100-106):**
```python
except RateLimitExhaustedError as e:
    logger.warning(
        "Crawler stopped gracefully due to API rate limit exhaustion",
        error=str(e),
    )
    sys.exit(0)  # Exit with success code
```

**Database persistence handler (main.py:165-170):**
```python
except RateLimitExhaustedError as e:
    logger.warning(
        "Rate limit exhausted - saving partial results",
        error=str(e),
    )
    raise
```

**Fallback mode handler (main.py:200-205):**
```python
except RateLimitExhaustedError as e:
    logger.warning(
        "Rate limit exhausted - saving partial results",
        error=str(e),
    )
    raise
```

## Behavior Flow

### Normal Rate Limit Hit During Crawling
1. Request returns rate limit error without "already exceeded"
2. `RateLimitError` is raised
3. Crawler waits 60 seconds and retries
4. Continues crawling after wait period

### Rate Limit Already Exhausted
1. Request returns rate limit error with "already exceeded"
2. `RateLimitExhaustedError` is raised
3. Pagination loop stops immediately
4. Crawl loop breaks (doesn't continue to next query)
5. Partial results are saved to database/CSV
6. Application exits with code 0 (success)
7. GitHub Actions job shows as successful

## GitHub Actions Integration

When running in GitHub Actions matrix jobs:

**Before:**
```
❌ Job fails with error code 1
❌ No partial results saved
❌ Other matrix jobs continue but aggregate fails
```

**After:**
```
✅ Job exits with code 0 (success)
✅ Partial results saved to database and CSV
✅ Results included in matrix aggregation
✅ Clean logs with clear rate limit message
```

## Testing

### Unit Tests

**File:** `tests/test_domain.py`

```python
def test_rate_limit_exhausted_error(self):
    """Test RateLimitExhaustedError exception."""
    with pytest.raises(RateLimitExhaustedError) as exc_info:
        raise RateLimitExhaustedError("API rate limit already exhausted")
    assert "already exhausted" in str(exc_info.value)
```

**File:** `tests/test_client.py`

```python
async def test_graphql_request_rate_limit_exhausted(self):
    """Test GraphQL request handles already exhausted rate limit."""
    # Mock response with "already exceeded" error
    mock_response_data = {
        "errors": [
            {
                "type": "RATE_LIMIT",
                "code": "graphql_rate_limit",
                "message": "API rate limit already exceeded for site ID installation.",
            }
        ]
    }
    # Verify RateLimitExhaustedError is raised
    with pytest.raises(RateLimitExhaustedError, match="already exhausted"):
        await client._make_graphql_request({"query": "test"})
```

### Test Coverage
- ✅ Exception type is properly defined
- ✅ Detection logic in GraphQL request handler
- ✅ Exception propagation through call stack
- ✅ Clean exit with success code

## Log Output Examples

### Graceful Shutdown Logs

```
ERROR:crawler.client:🛑 API rate limit already exhausted
ERROR:crawler.client:🛑 API rate limit exhausted - gracefully stopping crawler: API rate limit already exhausted: {'type': 'RATE_LIMIT', ...}
INFO:crawler.client:💾 Saving 247 repositories collected before rate limit
WARNING:crawler.main:Rate limit exhausted - saving partial results
WARNING:crawler.main:Crawler stopped gracefully due to API rate limit exhaustion
```

### Success Output

```
📊 Final discovery stats
  total_discovered: 247
  new_this_run: 247
✅ Export completed
✅ Job exits with code 0
```

## Configuration

No additional configuration required. The feature is automatic and enabled by default.

## Limitations

1. **No retry mechanism** - Once rate limit is exhausted, the job stops immediately
2. **No cross-job communication** - Other matrix jobs will not be notified
3. **Partial results only** - Job may collect fewer repositories than target

## Future Enhancements

Potential improvements for future versions:

1. **Rate limit prediction**: Check remaining rate limit before starting
2. **Dynamic sleep**: Calculate optimal wait time based on reset timestamp
3. **Job redistribution**: Reassign work from stopped jobs to jobs with quota
4. **Shared rate limit tracking**: Use GitHub Actions cache to track quota across jobs

## Related Files

- `crawler/domain.py` - Exception definitions
- `crawler/client.py` - Detection and handling logic
- `crawler/main.py` - Exit code management
- `tests/test_domain.py` - Exception tests
- `tests/test_client.py` - Integration tests

## References

- [GitHub GraphQL API Rate Limits](https://docs.github.com/en/graphql/overview/resource-limitations)
- [GitHub Actions Exit Codes](https://docs.github.com/en/actions/creating-actions/setting-exit-codes-for-actions)
- [Tenacity Retry Library](https://tenacity.readthedocs.io/)
