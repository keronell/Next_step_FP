"""dapr_client: conflict disambiguation + URL-safe keys, over httpx.MockTransport.

The conflict mapping burned twice against the live sidecar (409 vs ambiguous 500
"failed to set key"), so these tests pin the contract: only an OBSERVED collision
(key exists / etag moved on re-read) becomes DaprConflict; an outage with the
same error text stays DaprError so subscribers RETRY instead of ACKing a lost
record.
"""
import json
from urllib.parse import unquote

import httpx
import pytest

from common import dapr as dapr_client
from common.dapr import DaprConflict, DaprError

SET_FAIL = json.dumps(
    {"errorCode": "ERR_STATE_SAVE", "message": "failed to set key cas-x"}
)


def _mock(monkeypatch, handler):
    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://localhost:3500/v1.0"
    )
    monkeypatch.setattr(dapr_client, "_http", lambda: client)
    return client


def test_ambiguous_500_with_existing_key_is_conflict(monkeypatch):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(500, text=SET_FAIL)
        # verification read: the key exists -> a rival created it
        return httpx.Response(200, json={"n": 1}, headers={"etag": "1"})

    _mock(monkeypatch, handler)
    with pytest.raises(DaprConflict):
        dapr_client.save_state("cas-x", {"n": 2}, if_absent=True)


def test_ambiguous_500_with_absent_key_is_store_error(monkeypatch):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(500, text=SET_FAIL)
        return httpx.Response(204)  # verification read: key still absent -> outage

    _mock(monkeypatch, handler)
    with pytest.raises(DaprError) as exc:
        dapr_client.save_state("cas-x", {"n": 2}, if_absent=True)
    assert not isinstance(exc.value, DaprConflict)


def test_ambiguous_500_with_unmoved_etag_is_store_error(monkeypatch):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(500, text=SET_FAIL)
        return httpx.Response(200, json={"n": 1}, headers={"etag": "7"})

    _mock(monkeypatch, handler)
    # We sent etag 7 and the stored etag is still 7 -> nobody raced us -> outage.
    with pytest.raises(DaprError) as exc:
        dapr_client.save_state("cas-x", {"n": 2}, etag="7")
    assert not isinstance(exc.value, DaprConflict)


def test_409_is_conflict_without_verification_read(monkeypatch):
    reads = []

    def handler(request):
        if request.method == "POST":
            return httpx.Response(409, text="possible etag mismatch")
        reads.append(request.url.path)
        return httpx.Response(204)

    _mock(monkeypatch, handler)
    with pytest.raises(DaprConflict):
        dapr_client.save_state("cas-x", {"n": 2}, etag="1")
    assert reads == []  # 409 is trusted as-is


def test_outbound_api_token_attached_when_configured(monkeypatch):
    from common.config import get_settings

    monkeypatch.setenv("DAPR_ENABLED", "true")
    monkeypatch.setenv("DAPR_API_TOKEN", "sidecar-api-secret")
    get_settings.cache_clear()
    dapr_client._http.cache_clear()
    try:
        client = dapr_client._http()
        assert client.headers.get("dapr-api-token") == "sidecar-api-secret"
    finally:
        dapr_client._http.cache_clear()


def test_bulk_get_raises_on_per_item_error(monkeypatch):
    # Bulk responses are HTTP 200 even when items failed — silently skipping
    # them would truncate /my-submissions while reporting success.
    def handler(request):
        return httpx.Response(
            200,
            json=[
                {"key": "sub:a", "data": {"request_id": "a"}, "etag": "1"},
                {"key": "sub:b", "error": "redis timeout"},
            ],
        )

    _mock(monkeypatch, handler)
    with pytest.raises(DaprError):
        dapr_client.get_bulk_state(["sub:a", "sub:b"])


def test_keys_are_percent_encoded_in_urls(monkeypatch):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(204)

    _mock(monkeypatch, handler)
    weird = "idx:session:a/b?c#d"
    assert dapr_client.get_state(weird) is None
    dapr_client.delete_state(weird)
    assert len(seen) == 2
    for url in seen:
        # On the wire the whole key is ONE encoded path segment — no raw '/',
        # '?' or '#' that the sidecar would parse as URL syntax — and decoding
        # restores the exact key the JSON-body save wrote.
        assert url.endswith("/idx%3Asession%3Aa%2Fb%3Fc%23d")
        assert "?" not in url and "#" not in url
        assert unquote(url.rsplit("/", 1)[1]) == weird