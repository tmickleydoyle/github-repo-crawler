-- =====================================================
-- Migration 003: Expand Partition Column for Language Support
-- =====================================================
-- Expands the alphabet_partition column to support language-based filtering
--
-- This migration extends the partitioning system to support language filters
-- like "python,javascript,typescript" which exceed the original 10-character limit.
-- This enables more sophisticated crawling strategies beyond simple alphabet ranges.

-- =====================================================
-- Expand Partition Column Size
-- =====================================================
-- Increase column size to accommodate longer language filter strings
-- Example values: "python,javascript", "rust,go,c++", "matrix_job_42"
ALTER TABLE repo ALTER COLUMN alphabet_partition TYPE VARCHAR(100);

-- =====================================================
-- Update Documentation
-- =====================================================
-- Update the column comment to reflect its expanded purpose
COMMENT ON COLUMN repo.alphabet_partition IS 
    'Partition identifier used to crawl this repository. Can be:
     - Alphabet range (e.g., "a-c", "d-f")  
     - Language filter (e.g., "python,javascript,typescript")
     - Matrix job ID (e.g., "matrix_0", "matrix_42")
     Used for parallel processing and avoiding duplicate collection.';

-- =====================================================
-- Note: Existing indexes automatically adapt to the column type change
-- =====================================================
