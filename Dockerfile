# Hugging Face Spaces (Docker SDK) image for the Next Step FastAPI backend.
#
# Strategy (DEV-31 "Option A"): the ChromaDB store is BUILT INSIDE the image from
# the committed raw job JSON (data/jobs/raw/*.json) via build_rag.py, then read-only
# at runtime. No persistent volume needed; the store ships with the image and is
# regenerated on every rebuild, so it can never silently be empty (DEV-15).
#
# TLS terminates at HF's proxy — uvicorn runs plain HTTP with --proxy-headers.

FROM python:3.11-slim

# UTF-8 so build_rag's stats bar-chart can't crash the build on a non-UTF8 locale.
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/hf_cache

# Non-root user (HF Spaces best practice).
RUN useradd -m -u 1000 user

WORKDIR /app

# CPU-only torch first so sentence-transformers doesn't pull the multi-GB CUDA build.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# App + pipeline deps (chromadb, sentence-transformers, fastapi, uvicorn, ...).
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Pre-download the embedding model into the image so cold starts (after the 48h
# free-tier sleep) don't re-fetch it over the network.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Build the vector store from committed raw data. Supabase is intentionally unset
# here (build-time has no secrets) so this is a pure ChromaDB build. CWD=/app, so the
# store lands at /app/data/jobs/chroma.  (.dockerignore excludes any local chroma/
# so this is always a clean, reproducible build.)
COPY data/ ./data/
RUN python data/scripts/build_rag.py

# Fail the build LOUDLY if the store came out empty — Option A's whole point.
RUN python -c "import chromadb; n=chromadb.PersistentClient(path='data/jobs/chroma').get_collection('job_ads').count(); print('baked', n, 'docs'); assert n>0, 'REFUSING TO SHIP AN EMPTY STORE'"

# App code last so editing it doesn't invalidate the (slow) store-build layer.
COPY backend/ ./backend/

# Absolute path so the store resolves regardless of CWD (fixes the DEV-32 relative
# CHROMA_PATH fragility). Overrides the value in any baked .env.
ENV CHROMA_PATH=/app/data/jobs/chroma

# Load the embedding model purely from the baked cache — no HF Hub calls at startup.
# (The model was pre-downloaded above, so offline is correct; this makes cold starts
# deterministic and immune to HF Hub rate-limits/outages. Must come AFTER the download.)
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

RUN chown -R user:user /app
USER user

WORKDIR /app/backend
EXPOSE 7860

# --proxy-headers + trust HF's proxy so the app sees the original https scheme.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips=*"]
