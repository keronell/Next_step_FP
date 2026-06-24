"""Best-effort persistence of questionnaire submissions to Supabase.

Server-only writer using the service_role key. By contract `save_submission` never
raises: if Supabase is unconfigured or unreachable, it logs and returns so the
/submit response (recommendations) is never blocked — same graceful-degrade spirit
as the RAG-down fallback.

# ponytail: one `submissions` table, answers + recommendations stored as JSONB.
# Normalize into a per-career recommendations table only if analytics actually need it.
"""
from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def _client():
    """Lazily build the Supabase client once, or None if persistence is disabled."""
    settings = get_settings()
    if not settings.supabase_enabled:
        return None
    from supabase import create_client

    return create_client(settings.supabase_url, settings.supabase_service_key)


def save_submission(
    request_id: str, answers: dict, recommendations: list[dict]
) -> None:
    """Insert one submission row. Best-effort: swallows all errors after logging."""
    client = _client()
    if client is None:
        return
    try:
        client.table("submissions").insert(
            {
                "request_id": request_id,
                "answers": answers,
                "recommendations": recommendations,
            }
        ).execute()
    except Exception:  # noqa: BLE001 - persistence must never break the request
        logger.warning("Submission %s: failed to persist to Supabase", request_id, exc_info=True)
