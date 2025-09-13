-- =====================================================
-- Migration 005: Enhanced Repository Metadata Collection
-- =====================================================
-- Adds comprehensive GitHub repository metadata fields for richer data collection
--
-- This migration enhances the repository table to capture:
-- 1. Additional repository statistics (watchers, issues, etc.)
-- 2. Repository content metadata (description, homepage, topics)
-- 3. Repository configuration flags (archived, template, etc.)
-- 4. Language and technology information
-- 5. Size and network metrics

-- =====================================================
-- Add Repository Content and Description Fields
-- =====================================================
ALTER TABLE repo ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS homepage_url TEXT;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS topics TEXT[]; -- Array of topic names
ALTER TABLE repo ADD COLUMN IF NOT EXISTS languages TEXT[]; -- Array of language names

-- =====================================================
-- Add Repository Statistics Fields
-- =====================================================
ALTER TABLE repo ADD COLUMN IF NOT EXISTS watchers_count INTEGER DEFAULT 0;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS open_issues_count INTEGER DEFAULT 0;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS subscribers_count INTEGER DEFAULT 0;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS network_count INTEGER DEFAULT 0;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS size_kb INTEGER DEFAULT 0;

-- =====================================================
-- Add Repository Configuration Fields
-- =====================================================
ALTER TABLE repo ADD COLUMN IF NOT EXISTS default_branch VARCHAR(255) DEFAULT 'main';
ALTER TABLE repo ADD COLUMN IF NOT EXISTS visibility VARCHAR(20) DEFAULT 'public';
ALTER TABLE repo ADD COLUMN IF NOT EXISTS license_name VARCHAR(255);
ALTER TABLE repo ADD COLUMN IF NOT EXISTS primary_language VARCHAR(100);

-- =====================================================
-- Add Repository State Flags
-- =====================================================
ALTER TABLE repo ADD COLUMN IF NOT EXISTS is_fork BOOLEAN DEFAULT FALSE;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS is_disabled BOOLEAN DEFAULT FALSE;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS is_template BOOLEAN DEFAULT FALSE;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS has_issues BOOLEAN DEFAULT TRUE;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS has_projects BOOLEAN DEFAULT TRUE;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS has_wiki BOOLEAN DEFAULT TRUE;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS has_pages BOOLEAN DEFAULT FALSE;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS has_downloads BOOLEAN DEFAULT TRUE;

-- =====================================================
-- Add Timestamp Fields for Enhanced Tracking
-- =====================================================
ALTER TABLE repo ADD COLUMN IF NOT EXISTS pushed_at TIMESTAMP;
ALTER TABLE repo ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

-- =====================================================
-- Create Performance Indexes
-- =====================================================
-- Index for filtering by repository characteristics
CREATE INDEX IF NOT EXISTS idx_repo_language ON repo(primary_language);
CREATE INDEX IF NOT EXISTS idx_repo_license ON repo(license_name);
CREATE INDEX IF NOT EXISTS idx_repo_visibility ON repo(visibility);
CREATE INDEX IF NOT EXISTS idx_repo_is_fork ON repo(is_fork);
CREATE INDEX IF NOT EXISTS idx_repo_is_archived ON repo(is_archived);
CREATE INDEX IF NOT EXISTS idx_repo_is_template ON repo(is_template);

-- Index for statistics-based queries
CREATE INDEX IF NOT EXISTS idx_repo_watchers ON repo(watchers_count);
CREATE INDEX IF NOT EXISTS idx_repo_issues ON repo(open_issues_count);
CREATE INDEX IF NOT EXISTS idx_repo_size ON repo(size_kb);

-- Index for content-based searches
CREATE INDEX IF NOT EXISTS idx_repo_description ON repo USING gin(to_tsvector('english', description));
CREATE INDEX IF NOT EXISTS idx_repo_topics ON repo USING gin(topics);
CREATE INDEX IF NOT EXISTS idx_repo_languages ON repo USING gin(languages);

-- Index for temporal queries
CREATE INDEX IF NOT EXISTS idx_repo_pushed_at ON repo(pushed_at);
CREATE INDEX IF NOT EXISTS idx_repo_updated_at ON repo(updated_at);

-- =====================================================
-- Add Column Comments for Documentation
-- =====================================================
COMMENT ON COLUMN repo.description IS 'Repository description from GitHub';
COMMENT ON COLUMN repo.homepage_url IS 'Repository homepage URL';
COMMENT ON COLUMN repo.topics IS 'Array of repository topics/tags';
COMMENT ON COLUMN repo.languages IS 'Array of programming languages used';
COMMENT ON COLUMN repo.watchers_count IS 'Number of watchers';
COMMENT ON COLUMN repo.open_issues_count IS 'Number of open issues';
COMMENT ON COLUMN repo.subscribers_count IS 'Number of subscribers';
COMMENT ON COLUMN repo.network_count IS 'Total forks across the network';
COMMENT ON COLUMN repo.size_kb IS 'Repository size in kilobytes';
COMMENT ON COLUMN repo.default_branch IS 'Default branch name (main, master, etc.)';
COMMENT ON COLUMN repo.visibility IS 'Repository visibility (public, private, internal)';
COMMENT ON COLUMN repo.license_name IS 'Repository license name';
COMMENT ON COLUMN repo.primary_language IS 'Primary programming language';
COMMENT ON COLUMN repo.is_fork IS 'Whether repository is a fork';
COMMENT ON COLUMN repo.is_archived IS 'Whether repository is archived';
COMMENT ON COLUMN repo.is_disabled IS 'Whether repository is disabled';
COMMENT ON COLUMN repo.is_template IS 'Whether repository is a template';
COMMENT ON COLUMN repo.has_issues IS 'Whether issues are enabled';
COMMENT ON COLUMN repo.has_projects IS 'Whether projects are enabled';
COMMENT ON COLUMN repo.has_wiki IS 'Whether wiki is enabled';
COMMENT ON COLUMN repo.has_pages IS 'Whether GitHub Pages is enabled';
COMMENT ON COLUMN repo.has_downloads IS 'Whether downloads are enabled';
COMMENT ON COLUMN repo.pushed_at IS 'Last push timestamp';
COMMENT ON COLUMN repo.updated_at IS 'Last updated timestamp';

-- =====================================================
-- Update Table Comment
-- =====================================================
COMMENT ON TABLE repo IS 'Enhanced GitHub repository metadata with comprehensive field collection';