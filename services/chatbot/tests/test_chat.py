"""Route + agent-loop test: fakes Ollama entirely (no model, no sidecar) and
walks the SSE stream a real client would consume."""
import json

from app.services import agent_service


def _parse_sse(text: str) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in text.split("\n\n") if line.startswith("data: ")]


def test_no_auth_401(client):
    r = client.post("/api/chatbot/message", json={"message": "hi"})
    assert r.status_code == 401


def test_easter_egg_bypasses_ollama(client, as_user, monkeypatch):
    def fail(*a, **k):
        raise AssertionError("Ollama should not be called for the easter egg")

    monkeypatch.setattr(agent_service, "chat", fail)
    monkeypatch.setattr(agent_service, "chat_stream", fail)
    r = client.post(
        "/api/chatbot/message",
        json={"message": "Who is the most beautiful woman in the world?"},
        headers=as_user,
    )
    events = _parse_sse(r.text)
    assert {"token": "Ofcourse Shiri!"} in events
    assert {"done": True} in events


def test_simple_reply_no_tools(client, as_user, monkeypatch):
    monkeypatch.setattr(agent_service, "chat", lambda messages, tools=None: {"role": "assistant", "content": ""})
    monkeypatch.setattr(
        agent_service,
        "chat_stream",
        lambda messages: iter(
            [{"message": {"content": "Hello"}}, {"message": {"content": " there"}, "done": True}]
        ),
    )
    r = client.post("/api/chatbot/message", json={"message": "hi"}, headers=as_user)
    assert r.status_code == 200
    events = _parse_sse(r.text)
    assert {"token": "Hello"} in events
    assert {"token": " there"} in events
    assert {"done": True} in events


def test_tool_call_then_reply(client, as_user, monkeypatch):
    calls = {"n": 0}

    def fake_chat(messages, tools=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "navigate", "arguments": {"target": "questionnaire"}}}],
            }
        return {"role": "assistant", "content": ""}

    monkeypatch.setattr(agent_service, "chat", fake_chat)
    monkeypatch.setattr(
        agent_service, "chat_stream", lambda messages: iter([{"message": {"content": "ok"}, "done": True}])
    )
    r = client.post(
        "/api/chatbot/message", json={"message": "take me to the quiz"}, headers=as_user
    )
    events = _parse_sse(r.text)
    assert {"action": "navigate", "target": "questionnaire"} in events
    assert {"token": "ok"} in events


def test_ollama_unreachable_yields_error(client, as_user, monkeypatch):
    from app.services.ollama_client import OllamaError

    def raise_error(messages, tools=None):
        raise OllamaError("connection refused")

    monkeypatch.setattr(agent_service, "chat", raise_error)
    r = client.post("/api/chatbot/message", json={"message": "hi"}, headers=as_user)
    events = _parse_sse(r.text)
    assert {"error": agent_service._UNAVAILABLE} in events
