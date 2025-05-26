# Hierarchical Parallelization Strategy for GitHub Crawler

This document describes the enhanced hierarchical parallelization strategy that combines alphabetical partitioning with matrix parallelization and async workers to achieve maximum throughput and scalability.

## Strategy Overview

The hierarchical approach implements three levels of parallelization:

```
Level 1: Alphabetical Partitioning (10 workflows)
├── A-B Organizations → matrix-crawler-a-b.yml
├── C-D Organizations → matrix-crawler-c-d.yml
├── E-F Organizations → matrix-crawler-e-f.yml
├── G-H Organizations → matrix-crawler-g-h.yml
├── I-J Organizations → matrix-crawler-i-j.yml
├── K-L Organizations → matrix-crawler-k-l.yml
├── M-N Organizations → matrix-crawler-m-n.yml
├── O-P Organizations → matrix-crawler-o-p.yml
├── Q-R Organizations → matrix-crawler-q-r.yml
└── S-Z Organizations → matrix-crawler-s-z.yml
    │
    ├── Level 2: Matrix Parallelization (20 runners per alphabet)
    │   ├── Runner 0 → Partition 0-499
    │   ├── Runner 1 → Partition 500-999
    │   ├── ...
    │   └── Runner 19 → Partition 9500-9999
    │       │
    │       └── Level 3: Async Workers (per runner)
    │           ├── Worker 1 → Concurrent GraphQL queries
    │           ├── Worker 2 → Concurrent API calls
    │           └── Worker N → Async I/O operations
```

## Workflow Architecture

### 1. Master Coordination Workflow
**File:** `master-hierarchical-coordinator.yml`

- **Purpose:** Triggers all 10 alphabetical partition workflows simultaneously
- **Input Parameters:**
  - `total_repos_per_partition`: Repositories to collect per alphabet (default: 10,000)
  - `matrix_size`: Parallel runners per alphabet (default: 20)
  - `mode`: Crawling mode (`stars-only` or `full-archive`)

**Usage:**
```bash
# Trigger the master coordinator
gh workflow run master-hierarchical-coordinator.yml \
  --field total_repos_per_partition="10000" \
  --field matrix_size="20" \
  --field mode="stars-only"
```

### 2. Alphabetical Partition Workflows
**Files:** `matrix-crawler-{a-b,c-d,e-f,g-h,i-j,k-l,m-n,o-p,q-r,s-z}.yml`

Each alphabet workflow:
- Filters repositories by organization name using GraphQL queries
- Uses internal matrix parallelization with configurable runners
- Stores data in alphabet-specific databases (`github_crawler_ab`, `github_crawler_cd`, etc.)
- Produces consolidated results for that alphabet range

**Example GraphQL Filtering:**
```graphql
# For A-B partition
query: "stars:>0 user:a* OR user:b*"

# For S-Z partition  
query: "stars:>0 user:s* OR user:t* OR user:u* OR user:v* OR user:w* OR user:x* OR user:y* OR user:z*"
```

### 3. Final Global Consolidation Workflow
**File:** `final-global-consolidation.yml`

- **Purpose:** Merges results from all alphabet partitions into a global dataset
- **Features:**
  - Downloads artifacts from all alphabet workflows
  - Creates global consolidated CSV and JSON exports
  - Generates comprehensive summary reports
  - Provides global rankings and statistics

## Performance Benefits

### Throughput Improvements
- **Simultaneous Execution:** All 10 alphabet workflows run in parallel
- **Rate Limit Distribution:** API calls distributed across alphabet partitions
- **Reduced Contention:** Each partition operates independently

### Scalability Enhancements
- **Configurable Matrix Size:** Each alphabet can use different runner counts
- **Fault Isolation:** Failure in one alphabet doesn't affect others
- **Resource Optimization:** Can adjust resources per alphabet based on expected load

### Expected Performance Metrics
With default configuration (10 alphabets × 20 runners = 200 total runners):

| Metric | Single Matrix | Hierarchical | Improvement |
|--------|---------------|--------------|-------------|
| Total Runners | 40 | 200 | 5x |
| Parallel Workflows | 1 | 10 | 10x |
| API Rate Limit Impact | High | Distributed | ~10x reduction |
| Fault Tolerance | Single Point | Isolated | Much better |

## Data Organization

### Database Structure
Each alphabet partition uses its own database:
- `github_crawler_ab` (A-B organizations)
- `github_crawler_cd` (C-D organizations)
- `github_crawler_ef` (E-F organizations)
- `github_crawler_gh` (G-H organizations)
- `github_crawler_ij` (I-J organizations)
- `github_crawler_kl` (K-L organizations)
- `github_crawler_mn` (M-N organizations)
- `github_crawler_op` (O-P organizations)
- `github_crawler_qr` (Q-R organizations)
- `github_crawler_sz` (S-Z organizations)

### Output Artifacts
Each alphabet workflow produces:
```
partition-{alphabet}-{runner_id}-results/
├── partition_{alphabet}_{runner}_stars.csv
└── data/repos-{alphabet}-{runner}/*.tar.gz

github-crawler-matrix-{alphabet}-final-results/
├── final_{alphabet}_stars_data.csv
├── final_{alphabet}_stars_data.json
└── MATRIX_{ALPHABET}_RESULTS.md
```

Global consolidation produces:
```
github-crawler-global-hierarchical-results/
├── final_global_stars_data.csv
├── final_global_stars_data.json
├── global_ranked_repositories.csv
└── GLOBAL_SUMMARY.md
```

## Usage Instructions

### Step 1: Trigger Master Coordinator
Start the hierarchical crawl by running the master coordinator:

```bash
gh workflow run master-hierarchical-coordinator.yml \
  --field total_repos_per_partition="10000" \
  --field matrix_size="20" \
  --field mode="stars-only"
```

This will simultaneously trigger all 10 alphabet partition workflows.

### Step 2: Monitor Progress
Each alphabet workflow will:
1. Calculate matrix partitions
2. Run parallel crawlers (20 runners by default)
3. Consolidate results for that alphabet
4. Upload artifacts

### Step 3: Global Consolidation
After all alphabet workflows complete, run the final consolidation:

```bash
gh workflow run final-global-consolidation.yml \
  --field consolidate_mode="download-and-merge"
```

## Configuration Options

### Per-Alphabet Customization
Each alphabet workflow can be configured independently:

```yaml
env:
  TOTAL_REPOS: ${{ github.event.inputs.total_repos || '10000' }}
  MATRIX_SIZE: ${{ github.event.inputs.matrix_size || '20' }}
  ALPHABET_FILTER: "ab"  # Specific to each workflow
```

### Load Balancing
Adjust matrix sizes based on expected alphabet distribution:
- **A-B, S-Z:** Higher load (consider `matrix_size: 30`)
- **Q-R, I-J:** Lower load (consider `matrix_size: 10`)

### Resource Optimization
```yaml
# For high-load alphabets
matrix_size: "30"
total_repos: "15000"

# For low-load alphabets  
matrix_size: "10"
total_repos: "5000"
```

## Monitoring and Debugging

### Workflow Status
Monitor all workflows from the Actions tab:
- Master coordinator shows overall trigger status
- Each alphabet workflow shows its specific progress
- Global consolidation shows merge status

### Artifact Downloads
Each workflow uploads artifacts that can be downloaded for debugging:
```bash
# Download specific alphabet results
gh run download <run-id> --name partition-ab-0-results

# Download global results
gh run download <run-id> --name github-crawler-global-hierarchical-results
```

### Error Handling
- **Alphabet Isolation:** Errors in one alphabet don't affect others
- **Partition Recovery:** Individual matrix partitions can be re-run
- **Graceful Degradation:** Global consolidation works with partial data

## Migration from Single Matrix

To migrate from the original single matrix approach:

1. **Gradual Migration:** Start with a few alphabet workflows
2. **Validation:** Compare results between single and hierarchical approaches
3. **Full Deployment:** Once validated, use hierarchical for all crawls

### Backward Compatibility
The original `matrix-crawler.yml` workflow remains available for:
- Small-scale crawls
- Testing and development
- Fallback scenarios

## Future Enhancements

### Potential Improvements
1. **Dynamic Load Balancing:** Adjust matrix sizes based on real-time alphabet distribution
2. **Cross-Alphabet Deduplication:** Handle organizations that might appear in multiple alphabets
3. **Intelligent Alphabet Splitting:** Split high-load alphabets (e.g., S-Z) into smaller ranges
4. **Real-time Monitoring:** Dashboard showing progress across all alphabets

### Advanced Configurations
```yaml
# Example: Split S-Z into smaller ranges
matrix:
  alphabet_workflow:
    - { name: "S Organizations", filter: "s" }
    - { name: "T Organizations", filter: "t" }
    - { name: "U-Z Organizations", filter: "uz" }
```

## Performance Monitoring

### Key Metrics to Track
- **Workflow Completion Times:** Compare across alphabets
- **Repository Distribution:** Actual vs expected per alphabet
- **API Rate Limit Usage:** Monitor across all partitions
- **Resource Utilization:** CPU, memory, network per alphabet

### Expected Results
With 10 alphabets × 20 runners × 500 repos per runner:
- **Total Capacity:** 100,000 repositories
- **Parallel Execution:** All alphabets run simultaneously  
- **Completion Time:** Limited by slowest alphabet, not total volume
- **Fault Tolerance:** 90% success rate even if one alphabet fails

This hierarchical approach transforms the GitHub crawler from a single-threaded bottleneck into a massively parallel, fault-tolerant system capable of handling enterprise-scale repository discovery and analysis.
