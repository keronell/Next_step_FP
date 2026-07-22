"""auth-service: the one owner of identity — proxies Supabase GoTrue, the
user_profiles username store and the DEV-60 self-input profile.
Public: /api/auth/register|login|logout|me, /api/profile.
Internal: GET /internal/verify (token verification for the other services)."""
from app.routes import auth, internal, profile
from common.app_factory import create_app

app = create_app("Auth Service", [auth.router, profile.router, (internal.router, "")])
