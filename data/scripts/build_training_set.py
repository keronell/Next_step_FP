"""Phase 1 of the matching-module rework: build the training feature table.

Consumes data/training/silver_labels.parquet (LLM-panel silver labels — synthetic,
not expert ground truth) and replays every profile through the same pipeline the
backend uses at serve time:

    answers -> build_profile() -> MiniLM embedding -> ChromaDB query per career
            -> feature_builder.build_feature_vector()  (38 dims, shared with serving)

Outputs:
    data/training/train_features.parquet   one row per profile: features + labels + provenance
    data/training/dataset_metadata.json    feature version, Chroma snapshot pin, config

Notes:
- Market skills come from ChromaDB only. The serving path can additionally merge
  Postgres job_postings skill counts when Supabase is configured; this script runs
  without Supabase, matching the default (and test) serving configuration. Recorded
  in the metadata.
- Run from the repo root: python data/scripts/build_training_set.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from tqdm import tqdm

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.config import Settings  # noqa: E402
from app.data import load_careers  # noqa: E402
from app.services import feature_builder as fb  # noqa: E402
from app.services.profile import build_profile  # noqa: E402
from app.services.rag_service import RagService  # noqa: E402

TRAINING_DIR = REPO_ROOT / "data" / "training"
SILVER_PARQUET = TRAINING_DIR / "silver_labels.parquet"
OUT_PARQUET = TRAINING_DIR / "train_features.parquet"
OUT_METADATA = TRAINING_DIR / "dataset_metadata.json"


def chroma_snapshot(settings: Settings, rag: RagService) -> dict:
    """Pin the store generation: document count + sqlite file size/mtime. Train and
    serve must use the same generation or the semantic/skill features drift."""
    sqlite = Path(settings.chroma_path) / "chroma.sqlite3"
    stat = sqlite.stat() if sqlite.exists() else None
    return {
        "chroma_path": settings.chroma_path,
        "collection": settings.chroma_collection,
        "document_count": rag.count,
        "sqlite_size_bytes": stat.st_size if stat else None,
        "sqlite_mtime_utc": (
            datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat() if stat else None
        ),
        "embed_model": settings.embed_model,
        "rag_top_k": settings.rag_top_k,
    }


def main() -> None:
    if not SILVER_PARQUET.exists():
        raise SystemExit(f"{SILVER_PARQUET} not found — run panel_label_profiles.py first (Phase 0).")

    silver = pd.read_parquet(SILVER_PARQUET)
    careers = load_careers()
    settings = Settings()
    rag = RagService.create(settings)
    names = fb.feature_names(careers)

    rows = []
    for r in tqdm(silver.itertuples(), total=len(silver), desc="Building features"):
        answers = json.loads(r.answers_json)
        embedding = rag.encode(build_profile(answers))
        semantic: dict[str, float | None] = {}
        market: dict = {}
        for career in careers:
            sim, skills = rag.query_field(embedding, career["field"], settings.rag_top_k)
            semantic[career["id"]] = sim
            market[career["id"]] = skills

        vector = fb.build_feature_vector(answers, careers, semantic, market)
        row = dict(zip(names, vector))
        row.update({
            "profile_id": r.profile_id,
            "profile_source": r.profile_source,
            "label_top1": r.label_top1,
            "label_top2": r.label_top2,
            "consensus_votes": r.consensus_votes,
            "mean_confidence": r.mean_confidence,
            "label_source": r.label_source,
            "prompt_version": r.prompt_version,
        })
        rows.append(row)

    df = pd.DataFrame(rows)
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "feature_version": fb.FEATURE_VERSION,
        "n_features": len(names),
        "feature_names": names,
        "n_rows": len(df),
        "rows_by_source": df["profile_source"].value_counts().to_dict(),
        "rows_by_label": df["label_top1"].value_counts().to_dict(),
        "label_source": "synthetic_llm (silver labels — NOT expert ground truth)",
        "silver_prompt_versions": sorted(silver["prompt_version"].unique().tolist()),
        "market_skills_source": "chromadb_only (Supabase job_postings not merged in this run)",
        "chroma_snapshot": chroma_snapshot(settings, rag),
    }
    OUT_METADATA.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote {OUT_PARQUET} ({len(df)} rows x {len(names)} features + labels)")
    print(f"Wrote {OUT_METADATA}")
    print("Label distribution:", dict(df["label_top1"].value_counts()))


if __name__ == "__main__":
    main()
