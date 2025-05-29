-- =====================================================
-- Migration 004: Add name_with_owner Column and Auto-Population
-- =====================================================
-- Adds the name_with_owner field for GitHub API compatibility
--
-- This migration resolves the "'name_with_owner'" database insertion error by:
-- 1. Adding a name_with_owner column to store "owner/repository" format
-- 2. Creating a trigger to automatically populate it from owner + name fields
-- 3. Ensuring backward compatibility with existing data
--
-- The name_with_owner field matches GitHub's API format (e.g., "facebook/react")
-- and is essential for GitHub Actions workflow export functionality.

-- =====================================================
-- Add name_with_owner Column
-- =====================================================
-- Store the repository identifier in GitHub's "owner/name" format
ALTER TABLE repo ADD COLUMN IF NOT EXISTS name_with_owner TEXT;

-- Add documentation for the new column
COMMENT ON COLUMN repo.name_with_owner IS 
    'Repository identifier in GitHub format (owner/name), e.g., "facebook/react".
     Automatically populated from owner and name columns via trigger.';

-- =====================================================
-- Create Index for Efficient Queries
-- =====================================================
-- Enable fast lookups by the name_with_owner field (used in exports)
CREATE INDEX IF NOT EXISTS idx_repo_name_with_owner ON repo(name_with_owner);

-- =====================================================
-- Auto-Population Trigger Function
-- =====================================================
-- Create a function to automatically construct name_with_owner from owner + name
-- This ensures consistency and prevents manual errors
CREATE OR REPLACE FUNCTION update_name_with_owner()
RETURNS TRIGGER AS $$
BEGIN
    -- Automatically set name_with_owner = owner + '/' + name
    NEW.name_with_owner := NEW.owner || '/' || NEW.name;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add function documentation
COMMENT ON FUNCTION update_name_with_owner() IS 
    'Trigger function that automatically populates name_with_owner column 
     by concatenating owner and name fields with a forward slash.';

-- =====================================================
-- Create Trigger for Automatic Updates
-- =====================================================
-- Ensure name_with_owner is always correct on insert/update operations
DROP TRIGGER IF EXISTS trigger_update_name_with_owner ON repo;
CREATE TRIGGER trigger_update_name_with_owner
    BEFORE INSERT OR UPDATE ON repo
    FOR EACH ROW
    EXECUTE FUNCTION update_name_with_owner();

-- =====================================================
-- Backfill Existing Data
-- =====================================================
-- Update any existing repositories to populate name_with_owner field
-- This ensures backward compatibility with data inserted before this migration
UPDATE repo 
SET name_with_owner = owner || '/' || name 
WHERE name_with_owner IS NULL;

-- =====================================================
-- Verification Query (for manual testing)
-- =====================================================
-- Uncomment the following to verify the migration worked correctly:
-- SELECT id, owner, name, name_with_owner FROM repo LIMIT 5;
