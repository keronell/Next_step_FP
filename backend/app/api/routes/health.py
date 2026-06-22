from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    repo = getattr(request.app.state, "repository", None)
    return {
        "status": "ok",
        "service": "career-discovery-api",
        "rag_ready": repo is not None,
    }
