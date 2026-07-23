from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from common.auth_dep import get_current_user
from common.models.auth import UserResponse

from app.services.agent_service import run_turn

router = APIRouter(prefix="/chatbot")


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


@router.post("/message")
def send_message(
    body: ChatRequest,
    current_user: UserResponse = Depends(get_current_user),
    authorization: str = Header(...),
) -> StreamingResponse:
    """Streams the turn as SSE. Auth-gated (branch 5 of the plan) — chatbot-service
    holds no data of its own, so `authorization` (the SAME bearer token that just
    verified `current_user`) is forwarded as-is to roadmap/history's own auth-gated
    endpoints when a tool needs them (see app/services/tools.py)."""
    return StreamingResponse(
        run_turn(current_user, body.conversation_id, body.message, authorization),
        media_type="text/event-stream",
    )
