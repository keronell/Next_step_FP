"""FastAPI career-discovery API.

On startup it builds the RAG-backed career repository (loads the embedding model +
ChromaDB collection once). If the store isn't available, the app still starts and
serves /api/health, but /api/questionnaire/submit returns a controlled 503 — the
frontend falls back to its offline estimate.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import SAFE_UNAVAILABLE
from app.api.routes import health, questionnaire, roadmap
from app.core.config import get_settings
from app.core.logging import get_logger
from app.repositories.career_repository import CareerRepository
from app.services.rag_service import RagService, RagUnavailableError

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting career-discovery-api")
    try:
        rag = RagService.create(settings)
        app.state.repository = CareerRepository(rag, settings)
        logger.info("RAG repository ready")
    except RagUnavailableError as exc:
        app.state.repository = None
        logger.warning("RAG store unavailable, /submit will return 503: %s", exc)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Career Discovery API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(questionnaire.router, prefix="/api")
    app.include_router(roadmap.router, prefix="/api")

    @app.exception_handler(RagUnavailableError)
    async def _rag_unavailable(request: Request, exc: RagUnavailableError):
        logger.error("RAG failure on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": SAFE_UNAVAILABLE},
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        # Keep the stack trace in logs, never in the response body.
        logger.exception("Unexpected error on %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": SAFE_UNAVAILABLE},
        )

    return app


app = create_app()
