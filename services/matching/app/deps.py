"""Matching-service dependencies (state lives on app.state, set in lifespan)."""
from fastapi import HTTPException, Request, status

from common.auth_dep import SAFE_UNAVAILABLE


def get_repository(request: Request):
    """The RAG-backed career repository, or 503 while the store is unavailable."""
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=SAFE_UNAVAILABLE
        )
    return repo
