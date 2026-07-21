"""DEV-60 profile storage routes.

Same strategy as test_auth.py: Supabase is off by default (503 contract), and tests
that need it enabled patch profile_service._client with an in-memory fake.
"""
import pytest

from app.services import profile_service
from test_auth import _FakeClient  # the shared GoTrue fake, for token verification

TOKEN = {"Authorization": "Bearer fake-access-token"}
USER_ID = "user-uuid-123"  # _FakeUser.id — what get_current_user resolves to

PROFILE = {
    "experience": [
        {
            "role": "Data Analyst",
            "context": "a fintech",
            "duration_months": 24,
            "description": "built dashboards",
        }
    ],
    "projects": [{"name": "Dashboard", "description": "", "technologies": ["Tableau"]}],
    "skills": ["Python", "SQL"],
}


class _FakeProfileTable:
    """Minimal stand-in for the supabase-py query builder, backed by a dict."""

    def __init__(self, rows: dict, upserts: list):
        self._rows = rows
        self._filter = None
        self.last_upsert = upserts

    def select(self, *a, **k):
        return self

    def eq(self, _col, value):
        self._filter = value
        return self

    def upsert(self, row, *a, **k):
        self._rows[row["user_id"]] = row["profile"]
        self.last_upsert.append(row)
        return self

    def execute(self):
        class _Result:
            pass

        result = _Result()
        if self._filter is not None:
            stored = self._rows.get(self._filter)
            result.data = [{"profile": stored}] if stored is not None else []
        else:
            result.data = []
        return result


class _FakeDataClient:
    def __init__(self):
        self.rows: dict = {}
        self.upserts: list = []

    def table(self, _name):
        return _FakeProfileTable(self.rows, self.upserts)


@pytest.fixture
def store(monkeypatch):
    """Supabase 'enabled': GoTrue for the bearer token, a dict for the table."""
    fake_data = _FakeDataClient()
    fake_auth = _FakeClient()
    from app.services import auth_service

    monkeypatch.setattr(auth_service, "_get_auth_client", lambda: fake_auth)
    monkeypatch.setattr(auth_service, "_get_data_client", lambda: fake_auth)
    monkeypatch.setattr(profile_service, "_client", lambda: fake_data)
    return fake_data


# ── auth gate ─────────────────────────────────────────────────────────────────

def test_get_profile_requires_auth(client):
    assert client.get("/api/profile").status_code == 401


def test_put_profile_requires_auth(client):
    assert client.put("/api/profile", json=PROFILE).status_code == 401


def test_profile_unavailable_when_supabase_is_off(client, monkeypatch):
    """Default fixture leaves Supabase unconfigured — auth itself 503s first."""
    r = client.get("/api/profile", headers=TOKEN)
    assert r.status_code == 503


# ── round trip ────────────────────────────────────────────────────────────────

def test_empty_profile_for_a_user_who_never_saved(client, store):
    r = client.get("/api/profile", headers=TOKEN)
    assert r.status_code == 200
    assert r.json() == {"experience": [], "projects": [], "skills": []}


def test_put_then_get_round_trips(client, store):
    put = client.put("/api/profile", json=PROFILE, headers=TOKEN)
    assert put.status_code == 200
    assert put.json()["skills"] == ["Python", "SQL"]

    got = client.get("/api/profile", headers=TOKEN).json()
    assert got == put.json()
    assert got["experience"][0]["role"] == "Data Analyst"
    assert got["projects"][0]["technologies"] == ["Tableau"]


def test_put_is_last_write_wins(client, store):
    client.put("/api/profile", json=PROFILE, headers=TOKEN)
    client.put("/api/profile", json={"skills": ["Go"]}, headers=TOKEN)
    got = client.get("/api/profile", headers=TOKEN).json()
    assert got["skills"] == ["Go"]
    assert got["experience"] == []  # replaced wholesale, not merged


def test_clearing_is_an_empty_put(client, store):
    """No DELETE endpoint: the profile is one document, so empty PUT expresses it."""
    client.put("/api/profile", json=PROFILE, headers=TOKEN)
    client.put("/api/profile", json={}, headers=TOKEN)
    assert client.get("/api/profile", headers=TOKEN).json() == {
        "experience": [],
        "projects": [],
        "skills": [],
    }


def test_response_reflects_what_was_stored_not_what_was_sent(client, store):
    """Strips and caps are applied server-side; the client must render the truth."""
    r = client.put(
        "/api/profile",
        json={"skills": ["  Python  ", "python", ""], "experience": [{"role": " Analyst "}]},
        headers=TOKEN,
    )
    assert r.json()["skills"] == ["Python"]
    assert r.json()["experience"][0]["role"] == "Analyst"


def test_invalid_profile_is_rejected(client, store):
    r = client.put(
        "/api/profile",
        json={"projects": [{"name": f"p{i}"} for i in range(11)]},
        headers=TOKEN,
    )
    assert r.status_code == 422


def test_a_seeded_row_is_read_back_for_the_authenticated_user(client, store):
    """Pins USER_ID to whatever get_current_user actually resolves — without this,
    the corrupt-row test below would pass simply by looking up the wrong key."""
    store.rows[USER_ID] = {"experience": [], "projects": [], "skills": ["Rust"]}
    assert client.get("/api/profile", headers=TOKEN).json()["skills"] == ["Rust"]


def test_a_corrupt_stored_row_degrades_to_empty(client, store):
    """A row written under looser rules must not 500 the profile page."""
    store.rows[USER_ID] = {"skills": "not-a-list"}
    r = client.get("/api/profile", headers=TOKEN)
    assert r.status_code == 200
    assert r.json()["skills"] == []


def test_upsert_sets_updated_at_explicitly(client, store):
    """ON CONFLICT DO UPDATE writes only the columns sent, so the column default
    fires on INSERT only — without this, updated_at freezes at creation time."""
    client.put("/api/profile", json=PROFILE, headers=TOKEN)
    assert store.upserts[-1]["updated_at"]


def test_profile_service_503s_when_the_data_client_is_missing(monkeypatch):
    """Covers profile_service's own gate, which the route tests never reach: the
    auth dependency 503s first when Supabase is off, so this branch needs a unit."""
    from fastapi import HTTPException

    monkeypatch.setattr(profile_service, "get_supabase_client", lambda: None)
    with pytest.raises(HTTPException) as exc:
        profile_service.get_profile(USER_ID)
    assert exc.value.status_code == 503
