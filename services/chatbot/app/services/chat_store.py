"""Chat history: per-(user, conversation) message list in the Dapr state store,
one state entry at `chat:{user_id}:{conversation_id}` — TTL'd (session-scoped,
NOT durable account data, see CLAUDE.md's Redis-vs-Supabase split) and capped to
the last `chatbot_history_window` messages, since that's also the most the agent
ever replays into the model. Last-write-wins, no etag: a single user's own widget
never writes this key concurrently with itself.

Unlike roadmap progress, a missing/disabled state store degrades this to
memory-only (each turn loses prior context but still answers) rather than 503ing
the whole chat — persistence is a nice-to-have here, not the point of the feature.

Imported by name (not `common.dapr` itself) so tests can monkeypatch get_state/
save_state, mirroring roadmap_progress_service.
"""
from common.config import get_settings
from common.dapr import DaprError, enabled, get_state, save_state
from common.logging import get_logger

logger = get_logger(__name__)


def _key(user_id: str, conversation_id: str) -> str:
    return f"chat:{user_id}:{conversation_id}"


def get_history(user_id: str, conversation_id: str) -> list[dict]:
    """Return the stored message list ([{role, content}, ...]), or [] if none/unavailable."""
    if not enabled():
        return []
    try:
        data = get_state(_key(user_id, conversation_id))
        return data.get("messages", []) if data else []
    except DaprError as exc:
        logger.warning("Failed to fetch chat history for %s: %s", conversation_id, exc)
        return []


def save_history(user_id: str, conversation_id: str, messages: list[dict]) -> None:
    """Best-effort: replace the stored message list, trimmed to the sliding window."""
    if not enabled():
        return
    window = get_settings().chatbot_history_window
    try:
        save_state(
            _key(user_id, conversation_id),
            {"messages": messages[-window:]},
            ttl_seconds=get_settings().chatbot_history_ttl_seconds,
        )
    except DaprError as exc:
        logger.warning("Failed to save chat history for %s: %s", conversation_id, exc)
