from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    repo = getattr(request.app.state, "repository", None)
    return {
        "status": "ok",
        "service": "career-discovery-api",
        "rag_ready": repo is not None,
        # Job-ad count in the ChromaDB store; 0 means the offline fallback is active.
        "rag_doc_count": getattr(repo, "rag_count", 0) if repo is not None else 0,
    }
