"""Dapr pub/sub subscriber endpoints (DEV-38).

The sidecar calls GET /dapr/subscribe once at its startup to learn the
topic→route map, then POSTs each event as a CloudEvents 1.0 envelope
(payload under `data`) to the mapped route. These handlers are the async half
of persistence: submit/select publish (services/persistence.py), this router
writes the state store (services/submission_store.py).

Delivery is at-least-once — the store's writes are idempotent. Response bodies
tell the sidecar what happened: SUCCESS = ack, RETRY = redeliver, DROP = discard.

Mounted WITHOUT the /api prefix: this surface is sidecar-facing, and the DEV-43
gateway deliberately never routes /dapr/* or /events/*.

Trust boundary: events carry user_id, which the submit route only ever sets from
a verified token — so a forged event could plant records in another user's
history. When APP_API_TOKEN is set, every request must carry the sidecar's
`dapr-api-token` header (Dapr adds it to all app-channel calls); unset keeps the
dev default open, where uvicorn binds localhost only.
"""
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services import submission_store
from app.services.dapr_client import DaprError, enabled
from app.services.persistence import SELECTIONS_TOPIC, SUBMISSIONS_TOPIC

logger = get_logger(__name__)


def _require_sidecar(
    dapr_api_token: str | None = Header(None, alias="dapr-api-token"),
) -> None:
    expected = get_settings().app_api_token
    if not expected:
        return
    if not secrets.compare_digest(dapr_api_token or "", expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing dapr-api-token.",
        )


router = APIRouter(dependencies=[Depends(_require_sidecar)])

SUCCESS = {"status": "SUCCESS"}
RETRY = {"status": "RETRY"}
DROP = {"status": "DROP"}


@router.get("/dapr/subscribe")
def dapr_subscribe() -> list[dict]:
    if not enabled():
        return []
    pubsub = get_settings().dapr_pubsub
    return [
        {
            "pubsubname": pubsub,
            "topic": SUBMISSIONS_TOPIC,
            "routes": {"default": "/events/submissions"},
        },
        {
            "pubsubname": pubsub,
            "topic": SELECTIONS_TOPIC,
            "routes": {"default": "/events/selections"},
        },
    ]


async def _event_data(request: Request) -> dict | None:
    """The CloudEvents `data` payload, or None for anything malformed.

    Malformed messages must DROP, never 500: a raised handler makes Dapr
    redeliver the poison message forever.
    """
    try:
        envelope = await request.json()
    except Exception:  # noqa: BLE001 - invalid JSON body
        return None
    if not isinstance(envelope, dict):
        return None
    data = envelope.get("data")
    return data if isinstance(data, dict) else None


def _valid_submission(record: dict) -> bool:
    """Type-check the fields the store's key/time logic touches: truthiness
    alone lets e.g. a list through to a string comparison, and the resulting
    TypeError would 500 into infinite redelivery."""
    if not (isinstance(record.get("request_id"), str) and record["request_id"]):
        return False
    return all(
        record.get(field) is None or isinstance(record.get(field), str)
        for field in ("session_id", "user_id", "created_at", "selected_career")
    )


@router.post("/events/submissions")
async def on_submission(request: Request) -> dict:
    record = await _event_data(request)
    if record is None or not _valid_submission(record):
        logger.warning("malformed submissions event — dropping")
        return DROP
    try:
        # Threadpool: the store's state calls are sync httpx with a 5s timeout —
        # on the event loop a slow sidecar would stall every request in the app.
        await run_in_threadpool(submission_store.persist_submission, record)
        return SUCCESS
    except DaprError:
        logger.warning(
            "Failed to persist submission %s — requesting redelivery",
            record.get("request_id"),
            exc_info=True,
        )
        return RETRY
    except Exception:  # noqa: BLE001
        # Deterministic bugs don't heal by redelivery — drop, don't loop.
        logger.exception("Unexpected error persisting submission %s — dropping", record.get("request_id"))
        return DROP


@router.post("/events/selections")
async def on_selection(request: Request) -> dict:
    data = await _event_data(request)
    if data is None:
        logger.warning("malformed selections event — dropping")
        return DROP
    session_id = data.get("session_id")
    career_id = data.get("career_id")
    selected_at = data.get("selected_at")
    # All three must be non-empty STRINGS (selected_at feeds ISO-string
    # comparisons; a list would TypeError into infinite redelivery). Without the
    # click time the selection can't be scoped in time — fail closed.
    if not all(isinstance(v, str) and v for v in (session_id, career_id, selected_at)):
        logger.warning("malformed selections event — dropping")
        return DROP
    try:
        touched = await run_in_threadpool(
            submission_store.apply_selection, session_id, career_id, selected_at
        )
        logger.info("Selection %s applied to %d record(s) of session %s", career_id, touched, session_id)
        return SUCCESS
    except DaprError:
        logger.warning(
            "Failed to apply selection for session %s — requesting redelivery",
            session_id,
            exc_info=True,
        )
        return RETRY
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error applying selection for session %s — dropping", session_id)
        return DROP
