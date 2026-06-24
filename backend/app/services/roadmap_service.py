"""Roadmap lookup. The seam for later personalization.

Today: returns the curated static roadmap for a career id. Later: swap the body of
`get_roadmap` for a Claude-generated, profile-personalized roadmap — the signature
and the returned shape ({"sections": [...]}) stay the same so callers don't change.
"""
from app.data import load_roadmaps


def get_roadmap(career_id: str) -> dict | None:
    """Return {"sections": [...]} for a career, or None if there's no roadmap."""
    return load_roadmaps().get(career_id)
