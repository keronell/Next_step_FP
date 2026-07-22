-- DEV-60: self-input profile (experience, projects, skills), owned by auth-service.
--
-- One jsonb document per user: the three sections are always read and written
-- together by GET/PUT /api/profile, so splitting them into three tables would add
-- joins without enabling any query anyone makes.
--
-- Deliberate exception to the DEV-43 cutover (application data moved to the Dapr
-- state store): submissions are an event stream, whereas this is durable account
-- data the user edits directly — the same reason user_profiles stayed here.

create table if not exists public.user_profile_data (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  profile    jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.user_profile_data enable row level security;
-- No policies: service_role bypasses RLS (same pattern as user_profiles). The table
-- is only ever reached through auth-service, which scopes every query to the
-- caller's own user_id.
