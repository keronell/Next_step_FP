"""common.auth_dep: verification-by-invocation semantics (mocked dapr.invoke)."""
import httpx
import pytest
from fastapi import HTTPException

from common import auth_dep, dapr


def _response(status_code: int, body: dict) -> httpx.Response:
    return httpx.Response(status_code, json=body, request=httpx.Request("GET", "http://x"))


def test_verify_maps_200_to_user(monkeypatch):
    monkeypatch.setattr(
        auth_dep.dapr,
        "invoke",
        lambda *a, **k: _response(
            200, {"user_id": "u1", "email": "e@x.dev", "username": "n"}
        ),
    )
    user = auth_dep._verify("jwt")
    assert user.user_id == "u1"


def test_verify_maps_401_through(monkeypatch):
    monkeypatch.setattr(
        auth_dep.dapr, "invoke", lambda *a, **k: _response(401, {"detail": "Invalid token."})
    )
    with pytest.raises(HTTPException) as exc:
        auth_dep._verify("jwt")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token."


def test_verify_maps_invocation_failure_to_503(monkeypatch):
    def _down(*a, **k):
        raise dapr.DaprError("sidecar down")

    monkeypatch.setattr(auth_dep.dapr, "invoke", _down)
    with pytest.raises(HTTPException) as exc:
        auth_dep._verify("jwt")
    assert exc.value.status_code == 503


def test_verify_maps_auth_5xx_to_503(monkeypatch):
    monkeypatch.setattr(
        auth_dep.dapr, "invoke", lambda *a, **k: _response(503, {"detail": "Auth off."})
    )
    with pytest.raises(HTTPException) as exc:
        auth_dep._verify("jwt")
    assert exc.value.status_code == 503
    assert exc.value.detail == "Auth off."


def test_optional_returns_none_on_any_failure(monkeypatch):
    def _down(*a, **k):
        raise dapr.DaprError("sidecar down")

    monkeypatch.setattr(auth_dep.dapr, "invoke", _down)
    creds = type("C", (), {"credentials": "jwt"})()
    assert auth_dep.get_current_user_optional(creds) is None
    assert auth_dep.get_current_user_optional(None) is None
