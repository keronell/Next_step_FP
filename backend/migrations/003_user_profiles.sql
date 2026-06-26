create table if not exists public.user_profiles (
  user_id  uuid primary key references auth.users(id) on delete cascade,
  username text not null
);

create unique index if not exists user_profiles_username_lower_idx
  on public.user_profiles (lower(username));

alter table public.user_profiles enable row level security;
-- No policies: service_role bypasses RLS (same pattern as submissions table).
