-- =====================================================
-- Migration 001: Initial Database Schema
-- =====================================================
-- Creates the core tables for the GitHub crawler system
-- 
-- This migration establishes the foundational database structure for storing
-- GitHub repository metadata and star count statistics over time.

-- =====================================================
-- Core Repository Table
-- =====================================================
-- Stores fundamental repository metadata from GitHub
CREATE TABLE IF NOT EXISTS repo (
    id             BIGINT PRIMARY KEY,     -- GitHub repository ID (unique across all repos)
    name           TEXT NOT NULL,          -- Repository name (e.g., "my-project")
    owner          TEXT NOT NULL,          -- Repository owner/organization (e.g., "facebook")
    url            TEXT NOT NULL,          -- Full GitHub URL (e.g., "https://github.com/facebook/react")
    created_at     TIMESTAMP               -- When the repository was created on GitHub
);

-- =====================================================
-- Repository Statistics Table
-- =====================================================
-- Tracks star counts and other metrics over time for historical analysis
CREATE TABLE IF NOT EXISTS repo_stats (
    repo_id        BIGINT NOT NULL REFERENCES repo(id) ON DELETE CASCADE,
    fetched_date   DATE NOT NULL,          -- Date when these statistics were collected
    stars          INT NOT NULL,           -- Number of stars at this point in time
    
    -- Composite primary key allows tracking statistics over time
    PRIMARY KEY(repo_id, fetched_date)
);

-- =====================================================
-- Basic Performance Indexes
-- =====================================================
-- Index for efficient lookups by repository name and owner
CREATE INDEX IF NOT EXISTS idx_repo_name_owner ON repo(owner, name);

-- Index for efficient queries on repository statistics by date
CREATE INDEX IF NOT EXISTS idx_repo_stats_date ON repo_stats(fetched_date);

-- Index for efficient star count range queries
CREATE INDEX IF NOT EXISTS idx_repo_stats_stars ON repo_stats(stars);
