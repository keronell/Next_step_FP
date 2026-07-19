"""build_rag.resolve_store() must honor CHROMA_PATH / CHROMA_COLLECTION (so the
builder writes exactly where the backend reads) and otherwise fall back to the
repo-relative defaults. Loaded by path — the data pipeline isn't an importable package,
and resolve_store() imports no ChromaDB, so this stays offline-safe."""
import importlib.util
from pathlib import Path

import pytest

_BUILD_RAG = Path(__file__).resolve().parents[3] / "data" / "scripts" / "build_rag.py"


def _load_build_rag():
    spec = importlib.util.spec_from_file_location("build_rag_under_test", _BUILD_RAG)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_store_defaults(monkeypatch):
    monkeypatch.delenv("CHROMA_PATH", raising=False)
    monkeypatch.delenv("CHROMA_COLLECTION", raising=False)
    build_rag = _load_build_rag()

    path, collection = build_rag.resolve_store()
    assert path == Path("data/jobs/chroma")
    assert collection == "job_ads"


def test_resolve_store_honors_env(monkeypatch, tmp_path):
    target = tmp_path / "store"
    monkeypatch.setenv("CHROMA_PATH", str(target))
    monkeypatch.setenv("CHROMA_COLLECTION", "custom_ads")
    build_rag = _load_build_rag()

    path, collection = build_rag.resolve_store()
    assert path == target
    assert collection == "custom_ads"
