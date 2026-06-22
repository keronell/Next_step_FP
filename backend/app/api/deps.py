"""FastAPI dependencies. The career repository is built once at startup and stashed
on app.state; this resolves it (or returns a safe 503 if the RAG store never loaded)."""
from fastapi import HTTPException, Request, status

SAFE_UNAVAILABLE = "Career recommendations could not be generated at this time."


def get_repository(request: Request):
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=SAFE_UNAVAILABLE,
        )
    return repo
