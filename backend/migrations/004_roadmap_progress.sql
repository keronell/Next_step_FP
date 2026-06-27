-- Migration: roadmap_progress
-- Supabase MCP apply_migration name: create_roadmap_progress
--
-- Per-user roadmap completion: one row per (user_id, career_id) holding the
-- set of completed node ids. Anonymous users keep their progress in the
-- browser (localStorage) instead — only logged-in progress lands here.
--
-- Apply with:
--   Supabase MCP  →  apply_migration("create_roadmap_progress", <sql>)
--   or psql       →  \i backend/migrations/004_roadmap_progress.sql

create table if not exists public.roadmap_progress (
  user_id         uuid        not null references auth.users(id) on delete cascade,
  career_id       text        not null,
  completed_nodes text[]      not null default '{}',
  updated_at      timestamptz not null default now(),
  primary key (user_id, career_id)
);

alter table public.roadmap_progress enable row level security;
-- No policies: service_role bypasses RLS (same pattern as submissions/user_profiles).
