# Rate Limit Handling Flow

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Matrix Job                 │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           main.py: run() entry point                 │    │
│  │                                                       │    │
│  │  ┌────────────────────────────────────────────┐     │    │
│  │  │    GitHubClient.crawl()                    │     │    │
│  │  │                                             │     │    │
│  │  │  ┌──────────────────────────────────┐     │     │    │
│  │  │  │  For each search query:           │     │     │    │
│  │  │  │                                    │     │     │    │
│  │  │  │  _crawl_query()                   │     │     │    │
│  │  │  │    │                               │     │     │    │
│  │  │  │    ├─► search_repositories()      │     │     │    │
│  │  │  │    │     │                         │     │     │    │
│  │  │  │    │     └─► _make_graphql_request()   │     │    │
│  │  │  │    │           │                   │     │     │    │
│  │  │  │    │           ├─► POST to GitHub API   │     │    │
│  │  │  │    │           │                   │     │     │    │
│  │  │  │    │           └─► Response        │     │     │    │
│  │  │  │    │                │              │     │     │    │
│  │  │  │    │                ▼              │     │     │    │
│  │  │  │    │          ┌──────────┐        │     │     │    │
│  │  │  │    │          │ Error?   │        │     │     │    │
│  │  │  │    │          └─────┬────┘        │     │     │    │
│  │  │  │    │                │             │     │     │    │
│  │  │  │    │          ┌─────┴─────┐       │     │     │    │
│  │  │  │    │          │           │       │     │     │    │
│  │  │  │    │    ┌─────▼─────┐ ┌──▼────┐  │     │     │    │
│  │  │  │    │    │RATE_LIMIT │ │ Other │  │     │     │    │
│  │  │  │    │    │+ "already"│ │       │  │     │     │    │
│  │  │  │    │    │ exceeded  │ │       │  │     │     │    │
│  │  │  │    │    └─────┬─────┘ └───┬───┘  │     │     │    │
│  │  │  │    │          │           │       │     │     │    │
│  │  │  │    │          ▼           ▼       │     │     │    │
│  │  │  │    │  RateLimitExhausted  Other   │     │     │    │
│  │  │  │    │         Error       Error    │     │     │    │
│  │  │  │    │          │           │       │     │     │    │
│  │  │  │    └──────────┼───────────┘       │     │     │    │
│  │  │  │               │                   │     │     │    │
│  │  │  │               ▼                   │     │     │    │
│  │  │  │      ┌────────────────┐          │     │     │    │
│  │  │  │      │ Catch in       │          │     │     │    │
│  │  │  │      │ _crawl_query() │          │     │     │    │
│  │  │  │      │                │          │     │     │    │
│  │  │  │      │ raise (propagate)         │     │     │    │
│  │  │  │      └────────┬───────┘          │     │     │    │
│  │  │  │               │                  │     │     │    │
│  │  │  └───────────────┼──────────────────┘     │     │    │
│  │  │                  │                        │     │    │
│  │  │                  ▼                        │     │    │
│  │  │        ┌──────────────────┐              │     │    │
│  │  │        │ Catch in crawl() │              │     │    │
│  │  │        │                  │              │     │    │
│  │  │        │ Log warning      │              │     │    │
│  │  │        │ BREAK loop       │              │     │    │
│  │  │        │ (don't raise)    │              │     │    │
│  │  │        └────────┬─────────┘              │     │    │
│  │  │                 │                        │     │    │
│  │  │                 ▼                        │     │    │
│  │  │        Save repositories                 │     │    │
│  │  │        to database/CSV                   │     │    │
│  │  │                                          │     │    │
│  │  └──────────────────┬────────────────────────     │    │
│  │                     │                             │    │
│  │                     ▼                             │    │
│  │            Return CrawlResult                     │    │
│  │            (with partial data)                    │    │
│  │                                                   │    │
│  └───────────────────────┬───────────────────────────     │
│                          │                                │
│                          ▼                                │
│                 ┌────────────────┐                        │
│                 │ Catch in       │                        │
│                 │ run_with_db()  │                        │
│                 │                │                        │
│                 │ raise (propagate)                       │
│                 └────────┬───────┘                        │
│                          │                                │
│                          ▼                                │
│                 ┌────────────────┐                        │
│                 │ Catch in run() │                        │
│                 │                │                        │
│                 │ sys.exit(0)    │                        │
│                 └────────┬───────┘                        │
│                          │                                │
└──────────────────────────┼────────────────────────────────┘
                           │
                           ▼
                     ✅ Job Success
                     Exit Code: 0
```

## Key Decision Points

### 1. Error Detection (`_make_graphql_request`)

```python
if "RATE_LIMIT" in error_str:
    if "already exceeded" in error_str.lower():
        # 🛑 Pre-exhausted rate limit
        raise RateLimitExhaustedError()
    else:
        # ⏱️ Hit limit during crawling
        sleep(60)
        raise RateLimitError()  # Will retry
```

### 2. Pagination Handling (`_crawl_query`)

```python
try:
    result = await search_repositories(query)
except RateLimitExhaustedError:
    # Stop pagination immediately
    raise
except RateLimitError:
    # Wait and continue pagination
    await sleep(60)
    continue
```

### 3. Crawl Loop (`crawl`)

```python
for query in queries:
    try:
        await _crawl_query(query, ...)
    except RateLimitExhaustedError:
        # 💾 Save what we have
        logger.info(f"Saving {len(repos)} repositories")
        break  # Exit loop, don't raise
    except OtherError:
        continue  # Try next query
```

### 4. Exit Code (`run` in main.py)

```python
try:
    await run_with_database(...)
except RateLimitExhaustedError:
    logger.warning("Graceful shutdown")
    sys.exit(0)  # ✅ Success exit
```

## Comparison: Before vs After

### Before Implementation

```
GitHub API Request
    ↓
❌ Rate limit exhausted error
    ↓
Generic ApiError raised
    ↓
Logged as error
    ↓
Continue trying other queries
    ↓
Eventually fails with exit code 1
    ↓
❌ Job marked as FAILED
❌ Partial results not saved
```

### After Implementation

```
GitHub API Request
    ↓
🛑 Rate limit exhausted detected
    ↓
RateLimitExhaustedError raised
    ↓
Caught in crawl loop
    ↓
Break loop (save partial results)
    ↓
Database/CSV export proceeds
    ↓
Caught in main.py
    ↓
sys.exit(0)
    ↓
✅ Job marked as SUCCESS
✅ Partial results saved
```

## Error Message Examples

### Detection in GraphQL Response
```
{
  "errors": [
    {
      "type": "RATE_LIMIT",
      "code": "graphql_rate_limit", 
      "message": "API rate limit already exceeded for site ID installation."
    }
  ]
}
```

### Log Output
```
ERROR:crawler.client:🛑 API rate limit already exhausted
INFO:crawler.client:💾 Saving 247 repositories collected before rate limit
WARNING:crawler.main:Crawler stopped gracefully due to API rate limit exhaustion
```

### GitHub Actions Output
```
Run crawler job 42 of 100
🚀 Starting crawl...
✅ Collected 247 repositories
🛑 API rate limit exhausted - gracefully stopping
💾 Saving partial results
✅ Job completed with exit code 0
```

