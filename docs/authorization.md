# Role-based authorization (DEV-62)

Adds a role to every account so admin/elevated functionality can be gated. The
role lives in auth-service — the one service that owns identity — and rides on
the `UserResponse` every other service already gets back from `/internal/verify`.
No separate roles-service: a two-tier model doesn't justify a container + sidecar
+ network hop, and DEV-62 explicitly wants role checks in auth-service rather
than leaking across boundaries.

## Role model

| Role | Rank | Who | How assigned |
|---|---|---|---|
| `student` | 0 | every signup (the product's baseline user) | default, stamped at registration |
| `admin` | 100 | elevated/admin functionality | promoted out-of-band (see below) |

Privilege is **ordered**: a higher rank satisfies a lower-ranked gate (an admin
also passes a `student` gate). Ordering lives in one place per side —
`_ROLE_RANK` in `services/common/models/auth.py` and `ROLE_RANK` in
`frontend/src/contexts/AuthContext.jsx` — keep them in sync when adding tiers
(e.g. a `moderator` between the two). Add new roles to `VALID_ROLES` and the DB
hook's default handling as well.

The source of truth is the Supabase user's **`app_metadata.role`**.
`app_metadata` is server-controlled — a user cannot edit it — which is exactly
what makes it safe for authorization. `user_metadata` is user-editable and must
never be trusted for authz.

## How enforcement works

```
signup ──▶ create_user(app_metadata={role: student})   ← default assigned here
              │
login/verify ─┤  GoTrue get_user() returns app_metadata
              ▼
   auth_service._role_from_user() → normalize_role()    ← unknown/missing ⇒ student
              ▼
   UserResponse.role  ──▶ /me, /internal/verify, login token response
              ▼
   require_role("admin")  (services/common/auth_dep.py, and the auth-service
   mirror in services/auth/app/deps.py)                 ← 401 no token / 403 under-privileged
```

Backend enforcement reads the role **server-side** from `app_metadata` on the
`get_user()` call auth-service already makes. It therefore works **without** the
JWT hook being enabled — the hook (below) is only needed for the database path.

### Gating a route

```python
# in any service other than auth:
from common.auth_dep import require_role

@router.get("/admin/thing")
def admin_thing(user = Depends(require_role("admin"))):
    ...
```

The reference example lives at `GET /api/auth/admin/check` (auth-service). The
frontend guard primitive is `<RequireRole role="admin">…</RequireRole>`
(`frontend/src/components/RequireRole.jsx`) plus `useAuth().isAdmin` /
`hasRole(role)`. **The frontend guard only hides UI — it is not a security
boundary.** Every protected action must hit a backend route guarded by
`require_role`, which re-verifies the token and role.

## Custom Access Token Hook + RLS (DB path — forward-looking)

`backend/migrations/005_user_roles.sql` contains three things:

1. **Backfill** — stamps `role="student"` into `app_metadata` for existing users.
2. **`public.custom_access_token_hook`** — a Custom Access Token Auth Hook that
   injects the role as a top-level `user_role` JWT claim, so Postgres RLS
   (`auth.jwt() ->> 'user_role'`) and any future *local* JWT verification can
   authorize without an extra lookup.
3. **A commented reference RLS policy** using that claim.

> **RLS role-gating is inert today.** All data access in this codebase goes
> through the `service_role` Supabase client, which **bypasses RLS by design**
> (`services/common/supabase_client.py`), and the browser never queries Supabase
> directly. The hook + RLS are there so the day a user-scoped client is used
> (e.g. the SPA querying Supabase), the pattern is ready. Backend authorization
> does not depend on any of it.

### Applying the migration (deliberate, not automatic)

Run the SQL, then enable the hook (a one-time manual step — no SQL for it):

```
# 1. run the migration
Supabase MCP → apply_migration("create_user_roles", <005_user_roles.sql>)
# or: psql → \i backend/migrations/005_user_roles.sql

# 2. enable the hook
Dashboard → Authentication → Hooks → "Custom Access Token" →
  select public.custom_access_token_hook → enable
# (or Management API / config.toml: auth.hook.custom_access_token)
```

Until step 2, issued JWTs carry no `user_role` claim; backend authz still works
(it reads `app_metadata` server-side), but RLS policies would see `NULL`.

## Promoting a user to admin

There is no admin-management UI yet (nothing to manage — this ticket ships the
mechanism, not admin features). Promote a user by setting `app_metadata.role`:

```sql
-- by email
update auth.users
set raw_app_meta_data =
      coalesce(raw_app_meta_data, '{}'::jsonb) || jsonb_build_object('role', 'admin')
where email = 'someone@example.com';
```

or via the GoTrue admin API / Supabase dashboard (Authentication → Users → edit
the user's `app_metadata`). The new role takes effect on their next login (or
token refresh, once the hook is enabled). Demote by setting it back to
`'student'`.

## Follow-ups / not covered

- **Admin management surface** — no endpoint/UI to list users or toggle roles;
  promotion is manual SQL/dashboard for now. Worth a ticket once an admin
  feature actually needs it.
- **Local JWT verification** — auth-service still round-trips to GoTrue per
  request (`get_user()`). Once the hook is enabled, the other services could
  verify + read `user_role` from the JWT locally and skip the `/internal/verify`
  hop. Deliberately out of scope here; would change the verification contract.
