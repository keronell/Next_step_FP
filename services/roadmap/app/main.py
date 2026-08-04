"""roadmap-service: curated static roadmaps, DEV-59 market requirements (mined via
matching-service invocation), and per-user roadmap progress in the Dapr state
store."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routes import roadmap
from app.services.requirements_service import RequirementsService
from common.app_factory import create_app
from common.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Reads go through matching-service per request (lru-cached static roadmaps
    # + never-raising requirements) — nothing heavy to preload.
    app.state.requirements = RequirementsService(get_settings())
    yield


app = create_app("Roadmap Service", [roadmap.router], lifespan=lifespan)
