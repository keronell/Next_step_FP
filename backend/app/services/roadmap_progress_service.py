"""Roadmap progress: per-user completed-node sets, one row per (user_id, career_id).

Like auth_service (and unlike persistence.py), nothing here is best-effort — every
function raises HTTPException on failure so the caller gets a proper error response.
Anonymous users never reach this; their progress lives in the browser.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.core.logging import get_logger
from app.services.supabase_client import get_supabase_client

logger = get_logger(__name__)

_UNAVAILABLE = "Roadmap progress is unavailable — Supabase is not configured."


def _client():
    """Return the Supabase client or raise 503 if Supabase is not configured."""
    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_UNAVAILABLE,
        )
    return client


def get_progress(user_id: str, career_id: str) -> list[str]:
    """Return the completed node ids for a user's career roadmap, or [] if none."""
    client = _client()
    try:
        result = (
            client.table("roadmap_progress")
            .select("completed_nodes")
            .eq("user_id", user_id)
            .eq("career_id", career_id)
            .execute()
        )
        return result.data[0]["completed_nodes"] if result.data else []
    except Exception as exc:
        logger.warning(
            "Failed to fetch roadmap progress for %s/%s: %s", user_id, career_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve roadmap progress.",
        )


def save_progress(user_id: str, career_id: str, completed_nodes: list[str]) -> list[str]:
    """Upsert the full completed-node set for (user_id, career_id). Returns it back."""
    client = _client()
    try:
        client.table("roadmap_progress").upsert(
            {
                "user_id": user_id,
                "career_id": career_id,
                "completed_nodes": completed_nodes,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="user_id,career_id",
        ).execute()
        return completed_nodes
    except Exception as exc:
        logger.warning(
            "Failed to save roadmap progress for %s/%s: %s", user_id, career_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save roadmap progress.",
        )
