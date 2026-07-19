"""Shared FastAPI construction: CORS, safe 500 handler, /healthz.

Each service's main.py stays ~10 lines: routers + (optional) lifespan.
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from common.auth_dep import SAFE_UNAVAILABLE
from common.config import get_settings
from common.logging import get_logger, setup_logging

logger = get_logger(__name__)


def create_app(title: str, routers: list, *, lifespan=None) -> FastAPI:
    setup_logging()
    settings = get_settings()
    app = FastAPI(title=title, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for item in routers:
        router, prefix = item if isinstance(item, tuple) else (item, "/api")
        app.include_router(router, prefix=prefix)

    @app.get("/healthz")
    def healthz() -> dict:  # compose healthchecks + gateway wait-for-up
        return {"status": "ok"}

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        # Keep the stack trace in logs, never in the response body.
        logger.exception("Unexpected error on %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": SAFE_UNAVAILABLE},
        )

    return app
