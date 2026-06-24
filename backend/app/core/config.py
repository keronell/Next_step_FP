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

    # Supabase persistence (server-only). Empty = disabled; submissions just aren't saved.
    supabase_url: str = ""
    supabase_service_key: str = ""

    # OpenAI (roadmap generation). Empty = disabled; roadmaps fall back to static JSON.
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
