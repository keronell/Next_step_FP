"""Thin client for the Dapr sidecar HTTP API (state store, pub/sub, invocation).

Raw httpx against http://localhost:{DAPR_HTTP_PORT} — no dapr SDK; httpx is already
a direct dependency and the sidecar API is three small endpoints. All functions are
sync: every route that persists is a `def` handler (FastAPI threadpool), and the
sidecar is a localhost hop.

Gate: when `dapr_enabled` is False every call raises DaprError immediately (no
network). Callers own the semantics — persistence swallows, roadmap progress and
history translate to 503/500 (same split as the old supabase_enabled contract).

Tests monkeypatch the consumers' imported references (e.g. submission_store.get_state),
mirroring the old persistence._client pattern; nothing here needs a running sidecar.
"""
import json
from functools import lru_cache
from urllib.parse import quote

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class DaprError(RuntimeError):
    """Sidecar unreachable, disabled, or returned a non-2xx response."""


class DaprConflict(DaprError):
    """Optimistic-concurrency failure: the key changed since it was read
    (etag mismatch) or already exists (if_absent save). Callers retry."""


def enabled() -> bool:
    return get_settings().dapr_enabled


@lru_cache
def _http() -> httpx.Client:
    """One client per process. Raises DaprError when Dapr is disabled so a stray
    call in a Dapr-off environment can never hit a random localhost:3500."""
    settings = get_settings()
    if not settings.dapr_enabled:
        raise DaprError("Dapr is not enabled (set DAPR_ENABLED=true).")
    # DAPR_API_TOKEN: when the sidecar requires API auth, every call must carry
    # this header or the whole persistence layer 401s.
    headers = {"dapr-api-token": settings.dapr_api_token} if settings.dapr_api_token else None
    return httpx.Client(
        base_url=f"http://localhost:{settings.dapr_http_port}/v1.0",
        timeout=5.0,
        headers=headers,
    )


def _store(store: str | None) -> str:
    return store or get_settings().dapr_state_store


def save_state(
    key: str,
    value,
    *,
    store: str | None = None,
    ttl_seconds: int | None = None,
    etag: str | None = None,
    if_absent: bool = False,
) -> None:
    """Write one key. Default is last-write-wins. Pass `etag` (from
    get_state_with_etag) for compare-and-swap, or `if_absent=True` for
    create-only — both raise DaprConflict when they lose the race."""
    try:
        item: dict = {"key": key, "value": value}
        if ttl_seconds is not None:
            item["metadata"] = {"ttlInSeconds": str(ttl_seconds)}
        conditional = bool(etag) or if_absent
        if etag:
            item["etag"] = etag
            item["options"] = {"concurrency": "first-write"}
        elif if_absent:
            # Empirically verified on state.redis (1.17): etag "" + first-write
            # creates the key, and every later conditional write against it —
            # including another "" — conflicts. Caveat: a key BORN via a plain
            # (unconditional) save accepts one "" write before locking; we never
            # do that — every sub:/idx: key is born through this if_absent path,
            # so they are create-only from birth. (first-write with no etag field
            # at all silently overwrites — never use that form.)
            item["etag"] = ""
            item["options"] = {"concurrency": "first-write"}
        r = _http().post(f"/state/{_store(store)}", json=[item])
        if conditional and r.status_code >= 400:
            # Real sidecar responses: stale etag -> 409 "possible etag mismatch";
            # create-only collision -> 500 "failed to set key ..." (no "etag" in
            # the body!). But that 500 text is ambiguous — a genuine store failure
            # can carry it too, and misreading an outage as a lost race would let
            # persist_submission ACK an event whose record was never written. So
            # 409 is trusted, and the 500 case is disambiguated by re-reading the
            # key: only an observed collision (key exists / etag moved) is a
            # conflict; everything else stays DaprError so callers RETRY.
            text = r.text.lower()
            if r.status_code == 409 or "etag mismatch" in text:
                raise DaprConflict(f"save_state({key}) lost a concurrent write")
            if "failed to set key" in text and _lost_race(key, store, etag or None, if_absent):
                raise DaprConflict(f"save_state({key}) lost a concurrent write")
        r.raise_for_status()
    except DaprError:
        raise
    except Exception as exc:  # httpx transport + HTTP status errors
        raise DaprError(f"save_state({key}) failed: {exc}") from exc


def _lost_race(key: str, store: str | None, sent_etag: str | None, if_absent: bool) -> bool:
    """Disambiguate an ambiguous conditional-save failure by observing the key."""
    try:
        _, current = get_state_with_etag(key, store=store)
    except DaprError:
        return False  # can't verify -> treat as store failure (caller retries safely)
    if if_absent:
        return current is not None  # someone created it first
    return current != sent_etag  # someone moved it since we read


def get_state(key: str, *, store: str | None = None):
    """Return the stored JSON value, or None when the key does not exist (HTTP 204)."""
    return get_state_with_etag(key, store=store)[0]


def get_state_with_etag(key: str, *, store: str | None = None):
    """Return (value, etag) — (None, None) when the key does not exist."""
    try:
        # quote(): keys embed client-provided ids (session_id) — '/', '?', '#'
        # would otherwise be parsed as URL syntax and read a DIFFERENT key than
        # the JSON-body save wrote.
        r = _http().get(f"/state/{_store(store)}/{quote(key, safe='')}")
        if r.status_code in (204, 404) or not r.content:
            return None, None
        r.raise_for_status()
        return r.json(), r.headers.get("etag")
    except DaprError:
        raise
    except Exception as exc:
        raise DaprError(f"get_state({key}) failed: {exc}") from exc


def get_bulk_state(keys: list[str], *, store: str | None = None, parallelism: int = 10) -> dict:
    """Return {key: value} for the keys that exist. Missing keys are omitted."""
    if not keys:
        return {}
    try:
        r = _http().post(
            f"/state/{_store(store)}/bulk",
            json={"keys": keys, "parallelism": parallelism},
        )
        r.raise_for_status()
        out = {}
        for item in r.json():
            # Bulk responses are HTTP 200 even when individual items failed —
            # a silent skip here would truncate history and report success.
            if item.get("error"):
                raise DaprError(f"bulk get: item {item.get('key')} failed: {item['error']}")
            # Docs say `data`, older runtimes said `value` — accept both.
            value = item.get("data", item.get("value"))
            if isinstance(value, str):
                value = json.loads(value)
            if value is not None:
                out[item["key"]] = value
        return out
    except DaprError:
        raise
    except Exception as exc:
        raise DaprError(f"get_bulk_state({len(keys)} keys) failed: {exc}") from exc


def delete_state(key: str, *, store: str | None = None) -> None:
    try:
        r = _http().delete(f"/state/{_store(store)}/{quote(key, safe='')}")
        r.raise_for_status()
    except DaprError:
        raise
    except Exception as exc:
        raise DaprError(f"delete_state({key}) failed: {exc}") from exc


def publish(topic: str, data: dict, *, pubsub: str | None = None) -> None:
    try:
        name = pubsub or get_settings().dapr_pubsub
        r = _http().post(f"/publish/{name}/{topic}", json=data)
        r.raise_for_status()
    except DaprError:
        raise
    except Exception as exc:
        raise DaprError(f"publish({topic}) failed: {exc}") from exc


def invoke(
    app_id: str,
    method_path: str,
    *,
    method: str = "GET",
    json_body: dict | None = None,
    headers: dict | None = None,
) -> httpx.Response:
    """Service invocation: sidecar routes to {app_id}'s /{method_path}. The callee's
    status code propagates — the caller interprets the response."""
    try:
        return _http().request(
            method,
            f"/invoke/{app_id}/method/{method_path}",
            json=json_body,
            headers=headers,
        )
    except DaprError:
        raise
    except Exception as exc:
        raise DaprError(f"invoke({app_id}/{method_path}) failed: {exc}") from exc
