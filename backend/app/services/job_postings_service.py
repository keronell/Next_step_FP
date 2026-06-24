"""Read-side access to the Supabase `job_postings` table (written by the scraper).

Used by the matching pipeline to supplement ChromaDB's market-skill signal with
skills aggregated from Postgres. Every function degrades to an empty result when
Supabase is unconfigured/unreachable, so the ChromaDB-only path always still works.
"""
from collections import Counter

from app.core.logging import get_logger
from app.services.supabase_client import get_supabase_client

logger = get_logger(__name__)


def skill_counts(field: str, limit: int) -> Counter:
    """Aggregate skill frequencies from job_postings for one career field.

    Returns an empty Counter when Supabase is disabled, errors, or has no rows —
    callers (CareerRepository) then rely on ChromaDB alone.
    """
    client = get_supabase_client()
    if client is None:
        return Counter()
    try:
        # Postgres has no semantic ranking, so this is just a bounded sample of the
        # field's postings — enough to reinforce the curated skill-overlap signal.
        resp = (
            client.table("job_postings")
            .select("skills")
            .eq("field", field)
            .limit(limit)
            .execute()
        )
    except Exception:  # noqa: BLE001 - reads must never break a recommendation
        logger.warning("job_postings read for field %r failed", field, exc_info=True)
        return Counter()

    counts: Counter = Counter()
    for row in resp.data or []:
        for skill in row.get("skills") or []:  # jsonb -> list via supabase-py
            if skill:
                counts[str(skill).strip().lower()] += 1
    return counts
