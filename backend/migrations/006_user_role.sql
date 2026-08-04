-- DEV-62: authorization role per account, owned by auth-service.
--
-- Lives on user_profiles rather than in GoTrue app_metadata because
-- _fetch_profile() already reads this row on every token verification — the role
-- rides along in the same select, at no extra cost. It is therefore never baked
-- into a JWT: a promotion or demotion below takes effect on the user's very next
-- request, with no token to invalidate.
--
-- Roles are granted by SQL only. No endpoint writes this column (see
-- docs/adr/0003-admin-role.md), so the API has no privilege-escalation surface.
--
-- Apply with:
--   Supabase MCP  →  apply_migration("add_user_role", <sql>)
--   or psql       →  \i backend/migrations/006_user_role.sql

alter table public.user_profiles
  add column if not exists role text not null default 'user';

-- Separate statement so re-running the migration doesn't fail on the constraint.
alter table public.user_profiles
  drop constraint if exists user_profiles_role_check;

alter table public.user_profiles
  add constraint user_profiles_role_check check (role in ('user', 'admin'));

-- Bootstrap the first admin (edit the username, then run):
--   update public.user_profiles set role = 'admin' where username = 'ronen';
