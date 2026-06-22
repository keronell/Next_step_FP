"""Settings loaded from environment (.env). One place for all configurable knobs."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> repo root is three parents up from this file's dir
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ChromaDB store built by data/scripts/build_rag.py
    chroma_path: str = str(_REPO_ROOT / "data" / "jobs" / "chroma")
    chroma_collection: str = "job_ads"
    embed_model: str = "all-MiniLM-L6-v2"
    rag_top_k: int = 8

    # Comma-separated list of allowed frontend origins for CORS
    cors_origins: str = "http://localhost:3000"
    api_port: int = 8000
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
