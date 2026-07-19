"""job_postings reads are graceful: disabled/errors => empty Counter, never raise."""
from collections import Counter

from app.services import job_postings_service as svc


def test_skill_counts_empty_when_disabled(monkeypatch):
    monkeypatch.setattr(svc, "get_supabase_client", lambda: None)
    assert svc.skill_counts("Frontend Development", 8) == Counter()


def test_skill_counts_aggregates_and_lowercases(monkeypatch):
    class _Resp:
        data = [{"skills": ["React", "CSS"]}, {"skills": ["react", "TypeScript"]}]

    class _Client:
        def table(self, *a, **k):
            return self

        select = eq = limit = table

        def execute(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(svc, "get_supabase_client", lambda: _Client())
    counts = svc.skill_counts("Frontend Development", 8)
    assert counts == Counter({"react": 2, "css": 1, "typescript": 1})


def test_skill_counts_swallows_errors(monkeypatch):
    class _Boom:
        def table(self, *a, **k):
            return self

        select = eq = limit = table

        def execute(self, *a, **k):
            raise RuntimeError("supabase down")

    monkeypatch.setattr(svc, "get_supabase_client", lambda: _Boom())
    assert svc.skill_counts("Frontend Development", 8) == Counter()
