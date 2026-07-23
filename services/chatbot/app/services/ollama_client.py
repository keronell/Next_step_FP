"""Thin client for Ollama's /api/chat (native install on the host — see
common.config's ollama_base_url comment). Two modes, used deliberately
differently by agent_service:

- `chat()` (stream=False): used while the agent is still deciding whether to
  call tools — tool_calls arrive as one complete field on the message, so
  there's nothing to gain from streaming an intermediate turn.
- `chat_stream()` (stream=True): used ONLY for the final answer, so the user
  sees tokens arrive live (branch 10 of the plan) instead of a blank wait.

No SDK — raw httpx, same philosophy as common.dapr.
"""
import json
from collections.abc import Iterator

import httpx

from common.config import get_settings
from common.logging import get_logger

logger = get_logger(__name__)


class OllamaError(RuntimeError):
    """Ollama unreachable, timed out, or returned a non-2xx response."""


def _url(path: str) -> str:
    return f"{get_settings().ollama_base_url.rstrip('/')}{path}"


def chat(messages: list[dict], *, tools: list[dict] | None = None) -> dict:
    """One non-streaming turn. Returns the `message` object
    ({"role": "assistant", "content": str, "tool_calls": [...] | absent})."""
    settings = get_settings()
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "keep_alive": settings.ollama_keep_alive,
    }
    if tools:
        payload["tools"] = tools
    try:
        r = httpx.post(_url("/api/chat"), json=payload, timeout=settings.ollama_timeout_seconds)
        r.raise_for_status()
        return r.json()["message"]
    except Exception as exc:  # noqa: BLE001 - httpx transport + HTTP status errors
        raise OllamaError(f"Ollama chat call failed: {exc}") from exc


def chat_stream(messages: list[dict]) -> Iterator[dict]:
    """Yields each streamed chunk (Ollama's newline-delimited JSON objects),
    each shaped like {"message": {"role", "content"}, "done": bool, ...}."""
    settings = get_settings()
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": True,
        "keep_alive": settings.ollama_keep_alive,
    }
    try:
        with httpx.stream(
            "POST", _url("/api/chat"), json=payload, timeout=settings.ollama_timeout_seconds
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                yield json.loads(line)
    except OllamaError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise OllamaError(f"Ollama stream call failed: {exc}") from exc
