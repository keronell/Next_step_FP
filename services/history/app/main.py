"""history-service: owns submission persistence. Consumes the pub/sub topics
(subscriber endpoints + /dapr/subscribe), serves /api/auth/my-submissions and
/api/auth/claim-sessions. Talks only to the Dapr state store — no DB driver."""
from app.routes import history, subscriptions
from common.app_factory import create_app

app = create_app("History Service", [history.router, (subscriptions.router, "")])
