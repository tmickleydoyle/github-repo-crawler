# Supabase Setup Guide for GitHub Crawler

This guide walks you through setting up Supabase as your persistent database for the GitHub crawler.

## Prerequisites

1. **Supabase Account**: Sign up at [supabase.com](https://supabase.com)
2. **GitHub Repository**: Your crawler repository
3. **GitHub Token**: Personal access token with repo permissions

## Step 1: Create Supabase Project

1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Click **"New Project"**
3. Choose your organization
4. Fill in project details:
   - **Name**: `github-crawler-db` (or your preferred name)
   - **Database Password**: Generate a strong password (save this!)
   - **Region**: Choose closest to your location
5. Click **"Create new project"**
6. Wait for setup to complete (~2 minutes)

## Step 2: Get Connection Details

1. In your Supabase project dashboard
2. Go to **Settings** → **Database**
3. Find the **Connection Info** section
4. Copy the **Connection string** (it looks like):
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxx.supabase.co:5432/postgres
   ```

## Step 3: Configure Locally

Run the automated setup script:

```bash
python scripts/setup_supabase.py
```

This will:
- Prompt for your Supabase connection details
- Create/update your `.env` file
- Test the database connection
- Initialize the required tables

**Alternative: Manual Setup**

Create a `.env` file with:
```bash
# GitHub API
GITHUB_TOKEN=your_github_token_here

# Supabase Database
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.xxx.supabase.co:5432/postgres

# Crawler Settings
MAX_REPOS=1000
LOG_LEVEL=INFO
```

## Step 4: Test Locally

Run a small test crawl:

```bash
python -m crawler.main --repos 100 --matrix-total 2 --matrix-index 0
```

Check persistence is working:

```bash
python scripts/check_persistence.py
```

You should see:
```
📊 Discovery Statistics:
   • Total repositories discovered: 100
   • Discovered in last 24 hours: 100
   • Matrix jobs used: 1
```

## Step 5: GitHub Actions Setup

### Add Repository Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Add these secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `DATABASE_URL` | `postgresql://postgres:[PASSWORD]@db.xxx.supabase.co:5432/postgres` | Your Supabase connection string |
| `GITHUB_TOKEN` | `ghp_xxxxxxxxxxxx` | Your GitHub personal access token |

### Deploy Workflow

The workflow file `.github/workflows/crawler-hourly.yml` is already configured for Supabase!

**Test the workflow:**

1. Go to **Actions** tab in your repository
2. Find "Hourly Repository Crawler"
3. Click **"Run workflow"** → **"Run workflow"**
4. Watch the jobs run

## Step 6: Monitor and Scale

### View Database Tables

In Supabase dashboard:
1. Go to **Table Editor**
2. You'll see these tables:
   - `repo` - Repository information
   - `repo_stats` - Star count history
   - `discovered_repositories` - Persistence tracking

### Monitor Persistence Effectiveness

Check logs in GitHub Actions or run locally:
```bash
python scripts/check_persistence.py
```

Example output after several runs:
```
📊 Discovery Statistics:
   • Total repositories discovered: 25,847
   • Discovered in last 24 hours: 1,243
   • Repositories found multiple times: 2,156
   • Matrix jobs used: 50

🎯 Persistence Effectiveness:
   • Rediscovery rate: 8.3%
   • Recent activity: 4.8%
   ✅ Good - Low duplicate discovery rate
```

### Scale for 5M Repositories

For maximum scale, increase parallel jobs:

```yaml
# In .github/workflows/crawler-hourly.yml
strategy:
  matrix:
    # Increase from 50 to 200 parallel jobs
    matrix_index: [0, 1, 2, ..., 199]
```

**Expected Performance:**
- **200 parallel jobs** × **25,000 repos each** = **5M repository capacity**
- **Increasing efficiency** over time as persistence eliminates duplicates
- **Cost effective** - only processes new repositories after initial runs

## Troubleshooting

### Connection Issues

1. **Check IP Allowlist**: Supabase may restrict connections
   - Go to **Settings** → **Database** → **Connection pooling**
   - Add your IP or allow all IPs: `0.0.0.0/0`

2. **Verify Connection String**: Ensure password is correctly encoded
   - Special characters in passwords need URL encoding
   - Use the exact string from Supabase dashboard

3. **Test Connection**: Use the setup script's test feature
   ```bash
   python scripts/setup_supabase.py
   ```

### Performance Issues

1. **Pool Size**: Adjust in `.env`:
   ```bash
   DB_POOL_SIZE=20
   DB_MAX_OVERFLOW=40
   ```

2. **Rate Limiting**: GitHub API limits may cause slowdowns
   - Monitor rate limit in logs
   - Reduce `MAX_REPOS` if hitting limits frequently

### Database Growth

1. **Storage**: Monitor in Supabase dashboard
   - **1M repos** ≈ 500MB storage
   - **5M repos** ≈ 2.5GB storage

2. **Cleanup**: Remove old statistics if needed:
   ```sql
   DELETE FROM repo_stats WHERE fetched_date < NOW() - INTERVAL '30 days';
   ```

## Success Indicators

✅ **Setup Complete When:**
- Local test crawl works without errors
- `scripts/check_persistence.py` shows discovered repositories
- GitHub Actions run successfully
- Supabase tables contain data
- Persistence stats show low rediscovery rates

✅ **Production Ready When:**
- Multiple hourly runs complete successfully
- Persistence effectiveness > 90% (low rediscovery rate)
- Database contains 10,000+ repositories
- GitHub Actions matrix jobs distribute work evenly

Your Supabase-powered GitHub crawler is now ready to scale to millions of repositories with persistent, efficient discovery! 🚀