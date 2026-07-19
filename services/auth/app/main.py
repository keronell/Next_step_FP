"""auth-service: the one owner of identity — proxies Supabase GoTrue and the
user_profiles username store. Public: /api/auth/register|login|logout|me.
Internal: GET /internal/verify (token verification for the other services)."""
from app.routes import auth, internal
from common.app_factory import create_app

app = create_app("Auth Service", [auth.router, (internal.router, "")])
