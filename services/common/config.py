"""Settings loaded from environment (.env). One place for all configurable knobs."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> repo root is three parents up from this file's dir
_REPO_ROOT = Path(__file__).resolve().parents[2]  # services/common/config.py -> repo root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ChromaDB store built by data/scripts/build_rag.py
    chroma_path: str = str(_REPO_ROOT / "data" / "jobs" / "chroma")
    chroma_collection: str = "job_ads"
    embed_model: str = "all-MiniLM-L6-v2"
    rag_top_k: int = 8

    # Learned matcher artifact (data/scripts/export_model.py). Empty = disabled;
    # matching uses the deterministic formula (also the fallback on any model error).
    matcher_model_path: str = ""

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

    # Dapr sidecar (DEV-38). dapr_enabled=False = state/pub-sub calls are no-ops (persistence
    # off) or 503 (roadmap progress, history) — mirrors the supabase_enabled contract.
    # DAPR_HTTP_PORT is exported into the app process by `dapr run`; never hardcode 3500.
    dapr_enabled: bool = False
    dapr_http_port: int = 3500
    dapr_state_store: str = "statestore"
    dapr_pubsub: str = "pubsub"
    # Two independent Dapr auth directions, one env var each:
    # - APP_API_TOKEN (sidecar -> app): daprd sends it as `dapr-api-token` on every
    #   app-channel call; our subscriber endpoints verify it. Empty = open (dev:
    #   uvicorn binds localhost only); REQUIRED when the app binds 0.0.0.0.
    # - DAPR_API_TOKEN (app -> sidecar): when daprd requires API auth, every state/
    #   publish/invoke call must carry it; dapr_client attaches it when set.
    app_api_token: str = ""
    dapr_api_token: str = ""

    # Job-ad requirement enrichment (DEV-59). Per career field, skills are mined from
    # the job-ad corpus and classified by how often they appear across that field's ads:
    #   Required  = skill in >= requirements_required_ratio of the sampled ads
    #   Advantage = skill in [requirements_advantage_ratio, requirements_required_ratio)
    requirements_required_ratio: float = 0.4
    requirements_advantage_ratio: float = 0.15
    requirements_sample_size: int = 100   # max ads sampled per field (the % denominator)
    requirements_min_ads: int = 8         # below this, skip — the % would be unreliable
    requirements_max_per_bucket: int = 6  # cap items shown per Required/Advantage bucket

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
