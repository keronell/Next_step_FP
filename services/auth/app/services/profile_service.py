"""Durable storage for the DEV-60 self-input profile (`user_profile_data`).

Lives in auth-service because it is the only service holding a Supabase data-plane
client and the one that owns the user_id namespace — the same reason `user_profiles`
(usernames) lives here. This is a deliberate exception to the DEV-43 rule that
application data moved to the Dapr state store: submissions are an event stream,
whereas a profile is durable account data the user edits directly.

One jsonb row per user. The three sections are always read and written together, so
normalizing them into three tables would buy nothing.

Not best-effort: like the rest of auth-service, failures raise rather than degrade —
a silently dropped save would leave the user believing their profile was stored.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status

from common.logging import get_logger
from common.models.profile import UserProfile
from common.supabase_client import get_supabase_client

logger = get_logger(__name__)

TABLE = "user_profile_data"
_UNAVAILABLE = "Profiles are unavailable — Supabase is not configured."
_FAILED = "Could not save your profile. Please try again."


def _client():
    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_UNAVAILABLE
        )
    return client


def get_profile(user_id: str) -> UserProfile:
    """The user's stored profile, or an empty one when they have never saved.

    Stored rows are revalidated through UserProfile on the way out: the caps and
    strip rules can tighten over time, and a row written under the old rules must
    not re-enter the pipeline unchecked.
    """
    try:
        result = (
            _client().table(TABLE).select("profile").eq("user_id", user_id).execute()
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Profile read for %s failed: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your profile.",
        )

    if not result.data:
        return UserProfile()
    try:
        return UserProfile(**(result.data[0].get("profile") or {}))
    except Exception:  # noqa: BLE001 - a stale row must not 500 the whole page
        logger.warning("Stored profile for %s failed validation; returning empty", user_id)
        return UserProfile()


def save_profile(user_id: str, profile: UserProfile) -> UserProfile:
    """Upsert the user's profile (last write wins) and return what was stored.

    Returns the validated object rather than the request body so the client renders
    exactly what persisted — stripped strings, dropped blanks, applied caps.
    """
    try:
        _client().table(TABLE).upsert(
            {
                "user_id": user_id,
                "profile": profile.model_dump(),
                # Set explicitly: ON CONFLICT DO UPDATE only writes the columns sent,
                # so the column's `default now()` fires on INSERT only — leaving
                # updated_at frozen at creation time on every later save.
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Profile write for %s failed: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_FAILED
        )
    return profile
