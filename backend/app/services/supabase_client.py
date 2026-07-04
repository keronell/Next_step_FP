"""Shared lazy Supabase clients for server-side reads/writes.

Returns None when credentials are unset so every caller can degrade gracefully
(the app must run with an empty .env). persistence.py keeps its own builder for
backwards-compatible tests; this is the one new code should use.

Two distinct clients on purpose — they MUST NOT be the same instance:

- get_supabase_client(): the *data-plane* client. Always acts as service_role
  (RLS bypassed). NEVER call GoTrue user-session methods (sign_in_with_password,
  get_user, …) on it — supabase-py overwrites the client's PostgREST
  Authorization header with the signed-in user's JWT, which downgrades it to the
  `authenticated` role and re-enables RLS for every later .table() call.
- get_auth_client(): a separate instance used only for GoTrue auth. Its session
  state may be mutated freely without poisoning the data client's role.
"""
from functools import lru_cache

from app.core.config import get_settings


def _build():
    settings = get_settings()
    if not settings.supabase_enabled:
        return None
    from supabase import create_client

    return create_client(settings.supabase_url, settings.supabase_service_key)


@lru_cache
def get_supabase_client():
    """Service-role data-plane client (RLS bypassed). Tables only — no auth calls."""
    return _build()


@lru_cache
def get_auth_client():
    """Separate client for GoTrue user-session calls, isolated from the data client."""
    return _build()
