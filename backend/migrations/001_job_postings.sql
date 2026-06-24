-- Migration: job_postings
-- The scraped job ads (data/jobs/raw/*.json) persisted in Postgres so the backend
-- can query them via SQL alongside the ChromaDB vector store.
--
-- Apply with the Supabase MCP (apply_migration) or psql. Columns mirror the
-- normalized shape every scraper source writes:
--   id, source, field, title, company, description, tags, url, date, scraped_at, skills
-- `location` is included for forward-compat but is NOT currently populated by the
-- scraper. `date` is mapped to posted_date (free-form string; format varies per source).

create table if not exists public.job_postings (
  id           text primary key,            -- e.g. "remoteok_1131911"
  source       text,                        -- remoteok | jobicy | jobspy | ...
  field        text,                         -- canonical field, e.g. "Frontend Development"
  title        text,
  company      text,
  location     text,                         -- nullable; not yet emitted by the scraper
  description  text,
  tags         jsonb not null default '[]'::jsonb,
  skills       jsonb not null default '[]'::jsonb,
  url          text,
  posted_date  text,                         -- raw "date" string; formats vary by source
  scraped_at   timestamptz,
  ingested_at  timestamptz not null default now()
);

-- Matching filters by field, so index it.
create index if not exists job_postings_field_idx on public.job_postings (field);

-- Server-only table: service_role (the backend) bypasses RLS; enabling it with no
-- policies locks out anon/authenticated clients. Same pattern as public.submissions.
alter table public.job_postings enable row level security;
