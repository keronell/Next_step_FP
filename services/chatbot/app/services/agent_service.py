"""The agent loop: bounded tool-calling against Ollama, then a streamed final
answer. One generator per turn, yielding SSE `data: {...}\\n\\n` frames — see
app/routes/chat.py for how it's wired into a StreamingResponse.

Event shapes yielded (each one JSON `data:` frame):
  {"conversation_id": str}                                   - once, first
  {"action": "navigate", "target": ..., ...}                 - zero or more,
      as soon as the model calls the navigate tool (before the final answer,
      so the frontend can route immediately rather than waiting for prose)
  {"token": str}                                              - streamed answer
  {"error": str}                                              - unrecoverable
      failure this turn (Ollama unreachable/timed out); ends the stream
  {"done": true}                                              - normal end
"""
import json
import re
import uuid
from collections.abc import Iterator

from common.config import get_settings
from common.logging import get_logger
from common.models.auth import UserResponse

from app.services import chat_store, tools
from app.services.ollama_client import OllamaError, chat, chat_stream

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are the 'Next Step Helper', a chat assistant embedded in a career-roadmap "
    "app. You ONLY discuss the user's career roadmap, learning steps, and the "
    "career assessment/questionnaire. If asked about anything else, politely say "
    "you can only help with roadmap and career questions here.\n"
    "Always call get_roadmap_status before giving roadmap-specific advice — never "
    "guess what the user has completed. If the user has no roadmap yet, tell them "
    "to complete the assessment first and offer to take them there with the "
    "navigate tool.\n"
    "Keep replies short and plain: no emojis, no bold/italic markdown, no headers, "
    "at most one short list when steps genuinely need enumerating. Prefer 2-4 "
    "sentences of plain prose over a formatted breakdown."
)

_UNAVAILABLE = "The assistant is unavailable right now."

# Easter egg: a hardcoded match, not a system-prompt instruction — an LLM asked
# to "always answer X to Y" will still paraphrase or drop it under other prompt
# pressure (e.g. the on-topic guardrail above would otherwise fight it). Punctuation-
# and case-insensitive so "who's the most beautiful woman in the world??" still hits.
_EASTER_EGG_TRIGGER = "who is the most beautiful woman in the world"
_EASTER_EGG_REPLY = "Ofcourse Shiri!"


def _is_easter_egg(message: str) -> bool:
    normalized = re.sub(r"[^\w\s]", "", message).strip().lower()
    normalized = re.sub(r"\bwhos\b", "who is", normalized)
    return normalized == _EASTER_EGG_TRIGGER


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def run_turn(
    user: UserResponse, conversation_id: str | None, message: str, token: str
) -> Iterator[str]:
    settings = get_settings()
    conversation_id = conversation_id or uuid.uuid4().hex
    yield _sse({"conversation_id": conversation_id})

    history = chat_store.get_history(user.user_id, conversation_id)

    if _is_easter_egg(message):
        yield _sse({"token": _EASTER_EGG_REPLY})
        chat_store.save_history(
            user.user_id,
            conversation_id,
            [*history, {"role": "user", "content": message}, {"role": "assistant", "content": _EASTER_EGG_REPLY}],
        )
        yield _sse({"done": True})
        return

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": message}]

    try:
        for _ in range(settings.chatbot_max_tool_calls):
            reply = chat(messages, tools=tools.TOOL_SPECS)
            tool_calls = reply.get("tool_calls") or []
            if not tool_calls:
                break
            messages.append(reply)
            for call in tool_calls:
                name = call.get("function", {}).get("name", "")
                arguments = call.get("function", {}).get("arguments") or {}
                result = tools.execute(name, arguments, token=token)
                if name == "navigate" and "error" not in result:
                    yield _sse({"action": "navigate", **result})
                messages.append({"role": "tool", "content": json.dumps(result)})

        full_text = ""
        for chunk in chat_stream(messages):
            content = chunk.get("message", {}).get("content", "")
            if content:
                full_text += content
                yield _sse({"token": content})
            if chunk.get("done"):
                break
    except OllamaError:
        logger.warning("Ollama unavailable mid-turn for conversation %s", conversation_id, exc_info=True)
        yield _sse({"error": _UNAVAILABLE})
        return

    chat_store.save_history(
        user.user_id,
        conversation_id,
        [*history, {"role": "user", "content": message}, {"role": "assistant", "content": full_text}],
    )
    yield _sse({"done": True})
