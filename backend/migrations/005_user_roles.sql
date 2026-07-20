-- Migration: user_roles
-- Supabase MCP apply_migration name: create_user_roles
--
-- Role-based authorization (DEV-62). The role lives in each auth user's
-- app_metadata (server-controlled — a user cannot edit it, unlike user_metadata),
-- and auth-service reads it off the GoTrue user object it already fetches per
-- request. This migration adds the pieces Supabase itself needs:
--
--   1. backfill    — stamp role="student" into app_metadata for every existing
--                    account so no one is left with a missing/ambiguous claim.
--   2. auth hook   — a Custom Access Token Hook that injects the role as a top-
--                    level `user_role` JWT claim, so Postgres RLS (auth.jwt())
--                    and any future local JWT verification can authorize without
--                    an extra lookup.
--   3. RLS example — a commented reference policy showing how to gate a table on
--                    the injected claim.
--
-- NOT applied to any live project by this repo — apply deliberately:
--   Supabase MCP  →  apply_migration("create_user_roles", <sql>)
--   or psql       →  \i backend/migrations/005_user_roles.sql
--
-- AFTER running the SQL you must also ENABLE the hook (one-time, manual — there
-- is no SQL for it):
--   Dashboard → Authentication → Hooks → "Custom Access Token" →
--     select the `public.custom_access_token_hook` function and enable.
--   (or set it via the Management API / config.toml `auth.hook.custom_access_token`.)
-- Until the hook is enabled the JWT carries no `user_role` claim; auth-service
-- still authorizes correctly because it reads app_metadata.role server-side, but
-- RLS policies below would see NULL. See docs/authorization.md.

-- ---------------------------------------------------------------------------
-- 1. Backfill existing users to the default role (idempotent).
--    coalesce keeps any role already set; only fills where it's absent.
-- ---------------------------------------------------------------------------
update auth.users
set raw_app_meta_data =
      coalesce(raw_app_meta_data, '{}'::jsonb)
      || jsonb_build_object(
           'role',
           coalesce(raw_app_meta_data ->> 'role', 'student')
         )
where raw_app_meta_data ->> 'role' is null;

-- ---------------------------------------------------------------------------
-- 2. Custom Access Token Hook.
--    Supabase calls this with the pending token's claims and expects the
--    (possibly modified) claims back. We copy app_metadata.role into a
--    top-level `user_role` claim, defaulting to 'student'.
--    SECURITY DEFINER + locked-down grants per Supabase's hook guidance.
-- ---------------------------------------------------------------------------
create or replace function public.custom_access_token_hook(event jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  claims    jsonb;
  user_role text;
begin
  select coalesce(u.raw_app_meta_data ->> 'role', 'student')
    into user_role
  from auth.users u
  where u.id = (event ->> 'user_id')::uuid;

  claims := event -> 'claims';
  claims := jsonb_set(claims, '{user_role}', to_jsonb(coalesce(user_role, 'student')));

  return jsonb_set(event, '{claims}', claims);
end;
$$;

-- The auth admin (GoTrue) role must execute the hook; nobody else should.
grant usage on schema public to supabase_auth_admin;
grant execute on function public.custom_access_token_hook(jsonb) to supabase_auth_admin;
revoke execute on function public.custom_access_token_hook(jsonb) from authenticated, anon, public;

-- ---------------------------------------------------------------------------
-- 3. Reference RLS policy (COMMENTED — no admin-facing table exists yet).
--    NOTE: this codebase reads all data through the service_role client, which
--    BYPASSES RLS by design (see services/common/supabase_client.py). So RLS
--    role-gating is inert until/unless a user-scoped Supabase client is used
--    (e.g. the browser querying Supabase directly). Kept here as the pattern to
--    copy when that day comes — reads the claim the hook above injects.
-- ---------------------------------------------------------------------------
-- create policy "admins read all rows"
--   on public.some_admin_table
--   for select
--   to authenticated
--   using ((auth.jwt() ->> 'user_role') = 'admin');
