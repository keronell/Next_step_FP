"""Best-effort persistence of questionnaire submissions via Dapr pub/sub (DEV-38).

The submit/select routes publish an event to the local sidecar; the subscriber
(api/routes/subscriptions.py) consumes it and writes the state store — replacing
the old FastAPI BackgroundTasks + direct Supabase insert. By contract nothing
here ever raises: if Dapr is disabled or the sidecar is unreachable, it logs and
returns so the /submit response (recommendations) is never blocked — same
graceful-degrade spirit as the RAG-down fallback.

# ponytail: one state entry per submission + session/user index keys (see
# submission_store.py). Normalize further only if analytics actually need it.
"""
from common.dapr import enabled, publish
from common.logging import get_logger
from common.topics import SELECTIONS_TOPIC, SUBMISSIONS_TOPIC

logger = get_logger(__name__)


def save_submission(
    request_id: str,
    answers: dict,
    recommendations: list[dict],
    session_id: str | None,
    user_id: str | None,
    created_at: str,
    profile: dict | None = None,
) -> None:
    """Publish one full submission record. Best-effort: swallows all errors after logging.

    created_at MUST be minted by the request handler (UTC ISO-8601, so
    lexicographic == chronological): this function runs as a background task,
    and a late mint here would postdate claims/selections that the user made
    after receiving the response, breaking the marker time bounds.
    """
    if not enabled():
        return
    record = {
        "request_id": request_id,
        "answers": answers,
        "recommendations": recommendations,
        "session_id": session_id,
        "user_id": user_id,
        "selected_career": None,
        "created_at": created_at,
        # Snapshot of the DEV-60 profile that produced these recommendations. The
        # live profile row (auth-service) is mutable, so without this an edited
        # profile would leave past submissions unexplainable — same provenance
        # reasoning as the per-rec model_caveats.
        "profile": profile,
    }
    try:
        publish(SUBMISSIONS_TOPIC, record)
    except Exception:  # noqa: BLE001 - persistence must never break the request
        logger.warning("Submission %s: failed to publish", request_id, exc_info=True)


def save_selection(session_id: str, career_id: str, selected_at: str) -> None:
    """Publish the career a session picked. Best-effort: swallows all errors after logging.

    selected_at is the click time from the request handler; it rides in the
    event so the subscriber can scope the selection to submissions that already
    existed when the user clicked.

    # ponytail: the subscriber applies last-write-wins on every record of the
    # session — a session normally has one submission; add a selections history
    # only if analytics need every click.
    """
    if not enabled():
        return
    try:
        publish(
            SELECTIONS_TOPIC,
            {"session_id": session_id, "career_id": career_id, "selected_at": selected_at},
        )
    except Exception:  # noqa: BLE001 - persistence must never break the request
        logger.warning("Selection for session %s: failed to publish", session_id, exc_info=True)
