-- Migration: user_auth_link
-- Supabase MCP apply_migration name: add_user_auth_link
--
-- Adds a nullable user_id FK so logged-in users' submissions can be
-- linked to their auth.users row, and a created_at timestamp for
-- ordering history queries. Prior anonymous rows are unaffected
-- (user_id stays NULL; created_at defaults to now() on ALTER, which
-- is close enough for existing rows — exact times weren't tracked before).
--
-- Apply with:
--   Supabase MCP  →  apply_migration("add_user_auth_link", <sql>)
--   or psql       →  \i backend/migrations/002_user_auth_link.sql

alter table public.submissions
  add column if not exists user_id    uuid        references auth.users(id) on delete set null,
  add column if not exists created_at timestamptz not null default now();

-- Speed up "fetch all submissions for this user" queries.
create index if not exists submissions_user_id_idx on public.submissions (user_id);
