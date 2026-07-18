"""Roadmap progress: per-user completed-node sets, one state entry per (user_id, career_id).

Stored in the Dapr state store (DEV-38) at `progress:{user_id}:{career_id}` —
value `{completed_nodes, updated_at}`. Like auth_service (and unlike persistence.py),
nothing here is best-effort — every function raises HTTPException on failure so the
caller gets a proper error response. Anonymous users never reach this; their
progress lives in the browser.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status

from common.logging import get_logger

# Imported by name so tests can monkeypatch roadmap_progress_service.get_state etc.,
# mirroring the old get_supabase_client patching pattern.
from common.dapr import DaprError, enabled, get_state, save_state

logger = get_logger(__name__)

_UNAVAILABLE = "Roadmap progress is unavailable — the state store is not configured."


def _key(user_id: str, career_id: str) -> str:
    return f"progress:{user_id}:{career_id}"


def _require_enabled() -> None:
    """Raise 503 when the Dapr sidecar is not configured (was: Supabase off)."""
    if not enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_UNAVAILABLE,
        )


def get_progress(user_id: str, career_id: str) -> list[str]:
    """Return the completed node ids for a user's career roadmap, or [] if none."""
    _require_enabled()
    try:
        data = get_state(_key(user_id, career_id))
        return data.get("completed_nodes", []) if data else []
    except DaprError as exc:
        logger.warning(
            "Failed to fetch roadmap progress for %s/%s: %s", user_id, career_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve roadmap progress.",
        )


def save_progress(user_id: str, career_id: str, completed_nodes: list[str]) -> list[str]:
    """Store the full completed-node set for (user_id, career_id). Returns it back."""
    _require_enabled()
    try:
        save_state(
            _key(user_id, career_id),
            {
                "completed_nodes": completed_nodes,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return completed_nodes
    except DaprError as exc:
        logger.warning(
            "Failed to save roadmap progress for %s/%s: %s", user_id, career_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save roadmap progress.",
        )
