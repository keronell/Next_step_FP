"""auth-service: the one owner of identity — proxies Supabase GoTrue, the
user_profiles username store and the DEV-60 self-input profile.
Public: /api/auth/register|login|logout|me, /api/profile, /api/admin/users (DEV-62).
Internal: GET /internal/verify (token verification for the other services)."""
from app.routes import admin, auth, internal, profile
from common.app_factory import create_app

app = create_app(
    "Auth Service", [auth.router, profile.router, admin.router, (internal.router, "")]
)
