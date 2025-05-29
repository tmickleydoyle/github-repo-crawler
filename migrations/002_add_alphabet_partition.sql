-- =====================================================
-- Migration 002: Add Alphabet Partition Support
-- =====================================================
-- Adds partitioning capabilities for parallel crawling
--
-- This migration enables the crawler to partition repositories by alphabet
-- ranges (e.g., "a-c", "d-f") to enable parallel processing across multiple
-- worker jobs without duplication.

-- =====================================================
-- Add Partition Tracking Column
-- =====================================================
-- Track which alphabet partition was used to crawl each repository
-- This prevents duplicate collection and enables efficient re-crawling
ALTER TABLE repo ADD COLUMN IF NOT EXISTS alphabet_partition VARCHAR(10);

-- Add descriptive comment explaining the purpose
COMMENT ON COLUMN repo.alphabet_partition IS 'Alphabet range used to crawl this repository (e.g., "a-c", "d-f", "matrix_0")';

-- =====================================================
-- Performance Indexes for Partitioned Queries
-- =====================================================
-- Enable efficient filtering by alphabet partition
CREATE INDEX IF NOT EXISTS idx_repo_alphabet_partition ON repo(alphabet_partition);

-- Enable efficient queries combining partition and owner for duplicate detection
CREATE INDEX IF NOT EXISTS idx_repo_alphabet_owner ON repo(alphabet_partition, owner);
