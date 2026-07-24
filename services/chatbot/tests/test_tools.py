"""Tool implementations: mocked at the dapr.invoke seam (no sidecar, no other
service running) — mirrors how roadmap/history tests fake their own dependencies."""
from common import dapr
from app.services import tools


class _FakeResponse:
    def __init__(self, status_code: int, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def _route(monkeypatch, responses: dict):
    """responses: {(app_id, method_path_prefix): FakeResponse}. Matches on prefix
    so e.g. 'api/roadmap/frontend' also satisfies 'api/roadmap/frontend/progress'."""

    def fake_invoke(app_id, method_path, *, method="GET", headers=None, **_):
        for (want_app, want_prefix), resp in responses.items():
            if app_id == want_app and method_path.startswith(want_prefix):
                return resp
        raise AssertionError(f"unexpected invoke({app_id}, {method_path})")

    monkeypatch.setattr(dapr, "invoke", fake_invoke)


# --- get_roadmap_status ------------------------------------------------------

def test_get_roadmap_status_no_submissions(monkeypatch):
    _route(monkeypatch, {("history", "api/auth/my-submissions"): _FakeResponse(200, [])})
    result = tools.get_roadmap_status(token="Bearer t")
    assert result["has_roadmap"] is False


def test_get_roadmap_status_with_progress(monkeypatch):
    _route(
        monkeypatch,
        {
            ("history", "api/auth/my-submissions"): _FakeResponse(
                200,
                [{"selected_career": "frontend", "created_at": "2026-07-20T00:00:00Z", "recommendations": []}],
            ),
            ("roadmap", "api/roadmap/frontend/progress"): _FakeResponse(
                200, {"completed_nodes": ["html"]}
            ),
            ("roadmap", "api/roadmap/frontend"): _FakeResponse(
                200,
                {
                    "sections": [
                        {"id": "s1", "nodes": [{"id": "html"}, {"id": "css"}]},
                    ]
                },
            ),
        },
    )
    result = tools.get_roadmap_status(token="Bearer t")
    assert result == {
        "has_roadmap": True,
        "career_id": "frontend",
        "completed_steps": ["html"],
        "next_step": "css",
        "total_steps": 2,
    }


# --- get_step_details ---------------------------------------------------------

def test_get_step_details_found(monkeypatch):
    _route(
        monkeypatch,
        {
            ("history", "api/auth/my-submissions"): _FakeResponse(
                200, [{"selected_career": "frontend", "created_at": "t", "recommendations": []}]
            ),
            ("roadmap", "api/roadmap/frontend"): _FakeResponse(
                200,
                {"sections": [{"id": "s1", "nodes": [{"id": "css", "label": "CSS"}]}]},
            ),
        },
    )
    result = tools.get_step_details(token="Bearer t", step_id="css")
    assert result == {"id": "css", "label": "CSS"}


def test_get_step_details_no_roadmap(monkeypatch):
    _route(monkeypatch, {("history", "api/auth/my-submissions"): _FakeResponse(200, [])})
    result = tools.get_step_details(token="Bearer t", step_id="css")
    assert "error" in result


# --- navigate ------------------------------------------------------------------

def test_navigate_questionnaire():
    assert tools.navigate(token="Bearer t", target="questionnaire") == {"target": "questionnaire"}


def test_navigate_roadmap_resolves_career(monkeypatch):
    _route(
        monkeypatch,
        {
            ("history", "api/auth/my-submissions"): _FakeResponse(
                200, [{"selected_career": "backend", "created_at": "t", "recommendations": []}]
            )
        },
    )
    result = tools.navigate(token="Bearer t", target="roadmap", step_id="apis")
    assert result == {"target": "roadmap", "career_id": "backend", "step_id": "apis"}


def test_navigate_unknown_target():
    result = tools.navigate(token="Bearer t", target="somewhere")
    assert "error" in result


# --- execute() dispatch ---------------------------------------------------------

def test_execute_unknown_tool():
    result = tools.execute("delete_everything", {}, token="Bearer t")
    assert "error" in result


def test_execute_catches_downstream_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise dapr.DaprError("sidecar down")

    monkeypatch.setattr(tools, "_HANDLERS", {"get_roadmap_status": boom})
    result = tools.execute("get_roadmap_status", {}, token="Bearer t")
    assert "error" in result
