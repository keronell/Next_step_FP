"""Career matching via matching-service (Dapr service invocation).

Failure semantics mirror the monolith's RAG-down contract exactly: ANY
unavailability (sidecar down, matching down, matching 503) -> HTTP 503 with
SAFE_UNAVAILABLE, which the SPA answers with its offline estimate.
"""
from fastapi import HTTPException, status

from common import dapr
from common.auth_dep import SAFE_UNAVAILABLE
from common.logging import get_logger
from common.models.profile import UserProfile

logger = get_logger(__name__)

MATCHING_APP_ID = "matching"


def match_remote(
    answers: dict[str, int | None], profile: UserProfile | None = None
) -> list[dict]:
    body: dict = {"answers": answers}
    if profile is not None:
        body["profile"] = profile.model_dump()
    try:
        # A full match (embedding encode + per-career Chroma queries) runs ~6s in
        # the compose topology — well past the client's 5s default.
        r = dapr.invoke(
            MATCHING_APP_ID,
            "internal/match",
            method="POST",
            json_body=body,
            timeout=30.0,
        )
    except dapr.DaprError:
        logger.warning("matching-service invocation failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=SAFE_UNAVAILABLE
        )
    if r.status_code != 200:
        logger.warning("matching-service answered %d", r.status_code)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=SAFE_UNAVAILABLE
        )
    return r.json()["recommendations"]
