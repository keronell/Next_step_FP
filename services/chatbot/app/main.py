"""chatbot-service: the "next step helper" — a tool-calling agent (Ollama) that
answers roadmap/questionnaire questions and can tell the frontend to navigate,
using read-only Dapr invocations into roadmap-service and history-service."""
from app.routes import chat
from common.app_factory import create_app

app = create_app("Chatbot Service", [chat.router])
