-- 001_initial_schema.sql: creates all tables in one go

CREATE TABLE IF NOT EXISTS repo (
  id             BIGINT PRIMARY KEY,
  name           TEXT     NOT NULL,
  owner          TEXT     NOT NULL,
  url            TEXT     NOT NULL,
  created_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS repo_stats (
  repo_id        BIGINT    NOT NULL REFERENCES repo(id) ON DELETE CASCADE,
  fetched_date   DATE      NOT NULL,
  stars          INT       NOT NULL,
  PRIMARY KEY(repo_id, fetched_date)
);

CREATE TABLE IF NOT EXISTS repo_archives (
  repo_id        BIGINT    NOT NULL REFERENCES repo(id) ON DELETE CASCADE,
  fetched_date   DATE      NOT NULL,
  archive_path   TEXT      NOT NULL,
  PRIMARY KEY(repo_id, fetched_date)
);

CREATE TABLE IF NOT EXISTS repo_file_index (
  repo_id      BIGINT    NOT NULL REFERENCES repo(id) ON DELETE CASCADE,
  fetched_date DATE      NOT NULL,
  path         TEXT      NOT NULL,
  content_sha  TEXT      NOT NULL,
  PRIMARY KEY(repo_id, fetched_date, path)
);
