"""Shared lazy Supabase client for server-side reads/writes.

Returns None when credentials are unset so every caller can degrade gracefully
(the app must run with an empty .env). persistence.py keeps its own builder for
backwards-compatible tests; this is the one new code should use.
"""
from functools import lru_cache

from app.core.config import get_settings


@lru_cache
def get_supabase_client():
    settings = get_settings()
    if not settings.supabase_enabled:
        return None
    from supabase import create_client

    return create_client(settings.supabase_url, settings.supabase_service_key)
