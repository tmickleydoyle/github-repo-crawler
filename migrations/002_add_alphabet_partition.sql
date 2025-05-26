-- 002_add_alphabet_partition.sql: adds alphabet_partition tracking column

-- Add alphabet_partition column to repo table to track which alphabet partition crawled each repository
ALTER TABLE repo ADD COLUMN IF NOT EXISTS alphabet_partition VARCHAR(10);

-- Create index on alphabet_partition for efficient filtering
CREATE INDEX IF NOT EXISTS idx_repo_alphabet_partition ON repo(alphabet_partition);

-- Create composite index for efficient queries by alphabet partition and owner
CREATE INDEX IF NOT EXISTS idx_repo_alphabet_owner ON repo(alphabet_partition, owner);
