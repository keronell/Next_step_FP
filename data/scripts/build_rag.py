"""
RAG builder — embeds job ads with sentence-transformers and stores them in ChromaDB.

Run after scrape_job_ads.py and extract_skills.py.

Usage:
    python data/scripts/build_rag.py
    python data/scripts/build_rag.py --reset          # wipe and rebuild from scratch
    python data/scripts/build_rag.py --sources remoteok
    python data/scripts/build_rag.py --query "React developer" --field "Frontend Development"
"""

import argparse
import json
from pathlib import Path

CHROMA_DIR = Path("data/jobs/chroma")
JOB_ADS_DIR = Path("data/jobs/raw")
COLLECTION_NAME = "job_ads"
EMBED_MODEL = "all-MiniLM-L6-v2"
BATCH_SIZE = 64  # jobs per ChromaDB upsert call


def get_client(reset: bool = False):
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"  Deleted existing collection '{COLLECTION_NAME}'")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return client, collection


def load_embedding_model():
    from sentence_transformers import SentenceTransformer
    print(f"Loading embedding model '{EMBED_MODEL}'...")
    return SentenceTransformer(EMBED_MODEL)


def build_document(job: dict) -> str:
    """Build the text to embed — title + skills + truncated description."""
    parts = []
    if job.get("title"):
        parts.append(f"Job: {job['title']}")
    if job.get("field"):
        parts.append(f"Field: {job['field']}")
    if job.get("skills"):
        parts.append(f"Skills: {', '.join(job['skills'])}")
    if job.get("description"):
        # Keep first 400 chars — enough signal, avoids noise
        parts.append(job["description"][:400])
    return " | ".join(parts)


def build_metadata(job: dict) -> dict:
    """Flat metadata dict for ChromaDB (strings and numbers only)."""
    return {
        "source": job.get("source", ""),
        "field": job.get("field", ""),
        "title": job.get("title", "")[:200],
        "company": job.get("company", "")[:100],
        "url": job.get("url", "")[:300],
        "date": job.get("date", "")[:50],
        "skills": json.dumps(job.get("skills", [])),  # store as JSON string
        "scraped_at": job.get("scraped_at", ""),
    }


def load_all_jobs(sources: list[str] | None) -> list[dict]:
    # None means auto-discover every JSON in jobs/raw/
    if sources is None:
        paths = sorted(JOB_ADS_DIR.glob("*.json"))
    else:
        paths = [JOB_ADS_DIR / f"{s}.json" for s in sources]

    jobs = []
    for path in paths:
        if not path.exists():
            print(f"  Skipping {path.name} — not found.")
            continue
        with open(path, encoding="utf-8") as f:
            batch = json.load(f)
        print(f"  Loaded {len(batch)} jobs from {path.stem}")
        jobs.extend(batch)
    return jobs


def _supabase_client():
    """Build a Supabase client from env (loading backend/.env if present), or None
    when credentials are unset — keeps the pipeline working without Supabase."""
    import os

    repo_root = Path(__file__).resolve().parents[2]
    try:
        from dotenv import load_dotenv
        load_dotenv(repo_root / "backend" / ".env")
    except ImportError:
        pass

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not (url and key):
        return None
    from supabase import create_client
    return create_client(url, key)


def _to_row(job: dict) -> dict:
    """Map a scraped job dict to a job_postings row (raw 'date' -> posted_date,
    empty strings -> None so timestamptz parses)."""
    return {
        "id": job["id"],
        "source": job.get("source"),
        "field": job.get("field"),
        "title": job.get("title"),
        "company": job.get("company"),
        "location": job.get("location"),  # not currently emitted by the scraper
        "description": job.get("description"),
        "tags": job.get("tags", []),
        "skills": job.get("skills", []),
        "url": job.get("url"),
        "posted_date": job.get("date"),
        "scraped_at": job.get("scraped_at") or None,
    }


def upsert_to_supabase(jobs: list[dict], batch_size: int = 500) -> int:
    """Upsert jobs into the Supabase job_postings table (PK = id, so re-runs don't
    duplicate). No-op when Supabase is unconfigured. Returns count upserted."""
    client = _supabase_client()
    if client is None:
        print("  Supabase disabled (SUPABASE_URL/SUPABASE_SERVICE_KEY unset) — skipping Postgres upsert.")
        return 0

    rows = [_to_row(j) for j in jobs]
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            client.table("job_postings").upsert(batch).execute()
        except Exception as e:  # don't let a Postgres hiccup abort the ChromaDB build
            print(f"\n  Supabase upsert failed at batch starting {i}: {e}")
            return total
        total += len(batch)
        print(f"  Upserted {total}/{len(rows)} into Supabase job_postings...", end="\r")

    print()
    return total


def upsert_jobs(collection, model, jobs: list[dict]) -> int:
    """Embed and upsert jobs into ChromaDB in batches. Returns count upserted."""
    total = 0
    for i in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[i : i + BATCH_SIZE]

        ids = [j["id"] for j in batch]
        documents = [build_document(j) for j in batch]
        metadatas = [build_metadata(j) for j in batch]

        embeddings = model.encode(documents, show_progress_bar=False).tolist()

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        total += len(batch)
        print(f"  Upserted {total}/{len(jobs)} jobs...", end="\r")

    print()
    return total


def query_collection(collection, model, query_text: str, field: str | None, n_results: int = 5):
    """Query the RAG store and print results. Used for testing."""
    embedding = model.encode([query_text])[0].tolist()

    where = {"field": field} if field else None
    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    print(f"\nTop {n_results} results for: '{query_text}'" + (f" in '{field}'" if field else ""))
    print("-" * 60)
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        skills = json.loads(meta.get("skills", "[]"))[:5]
        print(f"  [{1 - dist:.2f}] {meta['title']} @ {meta['company']}")
        print(f"         Field: {meta['field']}")
        print(f"         Skills: {', '.join(skills)}")
        print(f"         URL: {meta['url']}")
        print()


def print_stats(collection) -> None:
    count = collection.count()
    print(f"\nCollection '{COLLECTION_NAME}': {count} documents in ChromaDB")

    # Field distribution
    if count == 0:
        return
    results = collection.get(include=["metadatas"], limit=count)
    field_counts: dict[str, int] = {}
    for meta in results["metadatas"]:
        field = meta.get("field", "Unknown")
        field_counts[field] = field_counts.get(field, 0) + 1

    print("Field distribution:")
    for field, cnt in sorted(field_counts.items(), key=lambda x: -x[1]):
        bar = "█" * (cnt // 5)
        print(f"  {field:<30} {cnt:>4}  {bar}")


def main():
    parser = argparse.ArgumentParser(description="Build ChromaDB RAG store from job ads")
    parser.add_argument(
        "--sources",
        nargs="+",
        default=None,
        help="Which source JSON files to include (default: all files in jobs/raw/)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe the existing collection and rebuild from scratch",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="After building, run a test query against the store",
    )
    parser.add_argument(
        "--field",
        type=str,
        default=None,
        help="Filter test query to a specific field (use with --query)",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only print collection stats, skip building",
    )
    args = parser.parse_args()

    _, collection = get_client(reset=args.reset)

    if args.stats_only:
        model = load_embedding_model()
        print_stats(collection)
        if args.query:
            query_collection(collection, model, args.query, args.field)
        return

    jobs = load_all_jobs(args.sources)
    if not jobs:
        print("No jobs found. Run scrape_job_ads.py first.")
        return

    jobs_without_skills = [j for j in jobs if not j.get("skills")]
    if jobs_without_skills:
        print(f"  Note: {len(jobs_without_skills)} jobs have no skills list — embedding from title+field+description only.")

    # Persist to Postgres before embedding (scrape -> raw JSON -> Supabase -> ChromaDB).
    print(f"\nUpserting {len(jobs)} jobs into Supabase job_postings...")
    upsert_to_supabase(jobs)

    model = load_embedding_model()
    print(f"\nUpserting {len(jobs)} jobs into ChromaDB...")
    upserted = upsert_jobs(collection, model, jobs)

    print_stats(collection)

    if args.query:
        query_collection(collection, model, args.query, args.field)
    else:
        # Default test queries
        print("\nRunning default test queries...")
        query_collection(collection, model, "React TypeScript frontend developer", "Frontend Development", n_results=3)
        query_collection(collection, model, "machine learning PyTorch NLP", "Machine Learning", n_results=3)

    print(f"\nDone. {upserted} jobs indexed in {CHROMA_DIR}")
    print("The RAG store is ready for use by the backend roadmap generator.")


if __name__ == "__main__":
    main()
