from app.services import chat_store


def _fake_state(monkeypatch, data: dict):
    monkeypatch.setattr(chat_store, "enabled", lambda: True)
    monkeypatch.setattr(chat_store, "get_state", lambda key: data.get(key))
    monkeypatch.setattr(
        chat_store, "save_state", lambda key, value, **kw: data.__setitem__(key, value)
    )
    return data


def test_get_history_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(chat_store, "enabled", lambda: False)
    assert chat_store.get_history("u1", "c1") == []


def test_get_history_empty_when_no_entry(monkeypatch):
    _fake_state(monkeypatch, {})
    assert chat_store.get_history("u1", "c1") == []


def test_save_then_get_roundtrip(monkeypatch):
    data = _fake_state(monkeypatch, {})
    messages = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    chat_store.save_history("u1", "c1", messages)
    assert data["chat:u1:c1"]["messages"] == messages
    assert chat_store.get_history("u1", "c1") == messages


def test_save_history_trims_to_window(monkeypatch):
    from common.config import get_settings

    monkeypatch.setattr(get_settings(), "chatbot_history_window", 2, raising=False)
    data = _fake_state(monkeypatch, {})
    messages = [{"role": "user", "content": str(i)} for i in range(5)]
    chat_store.save_history("u1", "c1", messages)
    assert data["chat:u1:c1"]["messages"] == messages[-2:]


def test_save_history_disabled_is_noop(monkeypatch):
    monkeypatch.setattr(chat_store, "enabled", lambda: False)
    saved = {}
    monkeypatch.setattr(chat_store, "save_state", lambda *a, **k: saved.setdefault("called", True))
    chat_store.save_history("u1", "c1", [{"role": "user", "content": "hi"}])
    assert "called" not in saved
