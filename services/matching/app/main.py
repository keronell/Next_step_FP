"""matching-service: owns the ChromaDB store, embedding model, career matching,
and the learned matcher. Public surface: GET /api/health. Internal (invocation
only): POST /internal/match, GET /internal/field-skills/{field}."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.repositories.career_repository import CareerRepository
from app.routes import health, internal
from app.services.matcher import MatcherModelError, load_matcher
from app.services.rag_service import RagService, RagUnavailableError
from common.app_factory import create_app
from common.auth_dep import SAFE_UNAVAILABLE
from common.config import get_settings
from common.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "RAG store: path=%s collection=%s", settings.chroma_path, settings.chroma_collection
    )
    try:
        rag = RagService.create(settings)
        app.state.rag = rag
        app.state.repository = CareerRepository(rag, settings)
        logger.info("RAG repository ready (%d job ads)", rag.count)
    except RagUnavailableError as exc:
        app.state.rag = None
        app.state.repository = None
        logger.error(
            "RAG store unavailable at '%s' — /internal/match returns 503 and the "
            "frontend falls back to its offline estimate. Build it with "
            "`python data/scripts/build_rag.py`. Cause: %s",
            settings.chroma_path,
            exc,
        )

    app.state.matcher_model = None
    if settings.matcher_model_path:
        try:
            app.state.matcher_model = load_matcher(settings.matcher_model_path)
            logger.info("Learned matcher loaded: %s", app.state.matcher_model.version)
        except MatcherModelError as exc:
            logger.warning("Matcher model unavailable, using formula: %s", exc)
    else:
        logger.info("MATCHER_MODEL_PATH unset — matching uses the deterministic formula")
    yield


app = create_app("Matching Service", [health.router, (internal.router, "")], lifespan=lifespan)


@app.exception_handler(RagUnavailableError)
async def _rag_unavailable(request: Request, exc: RagUnavailableError):
    logger.error("RAG failure on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": SAFE_UNAVAILABLE},
    )
