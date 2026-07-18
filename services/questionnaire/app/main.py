"""questionnaire-service: serves the question bank and receives submissions.
No heavy dependencies — matching is invoked, persistence is published."""
from app.routes import questionnaire, questions
from common.app_factory import create_app

app = create_app("Questionnaire Service", [questionnaire.router, questions.router])
