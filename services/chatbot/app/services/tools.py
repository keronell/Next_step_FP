"""The agent's tool surface: read-only lookups + a client-navigation directive.
No tool mutates anything (DEV-?? chatbot scope decision) — mirrors the pattern
common.auth_dep uses for identity: chatbot-service holds no data of its own,
it invokes history-service and roadmap-service via Dapr on the caller's behalf,
forwarding the SAME bearer token those services already verify themselves.

`execute()` never raises for a *handled* failure (unknown tool, no roadmap yet,
downstream service error) — it returns {"error": ...} instead, which the agent
loop feeds back to the model so it can respond in natural language rather than
aborting the turn (see agent_service.run_turn).
"""
from common import dapr
from common.logging import get_logger

logger = get_logger(__name__)

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "get_roadmap_status",
            "description": (
                "Get the current user's career track, completed roadmap steps, and "
                "next step. Call this before giving any roadmap-specific advice — "
                "never guess what the user has or hasn't done."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_step_details",
            "description": (
                "Get the description and learning resources for one step (node) in "
                "the user's current roadmap."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "step_id": {
                        "type": "string",
                        "description": "The roadmap step id, e.g. 'javascript'.",
                    }
                },
                "required": ["step_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": (
                "Send the user to a page in the app: 'questionnaire' to take the "
                "career assessment, or 'roadmap' to view their current roadmap "
                "(optionally scrolled to a specific step_id)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "enum": ["questionnaire", "roadmap"]},
                    "step_id": {
                        "type": "string",
                        "description": "Optional step id to jump to; only used when target is 'roadmap'.",
                    },
                },
                "required": ["target"],
            },
        },
    },
]


def _latest_submission(token: str) -> dict | None:
    """Most recent completed assessment, or None if the user has never submitted one."""
    r = dapr.invoke("history", "api/auth/my-submissions", headers={"Authorization": token})
    if r.status_code != 200:
        raise RuntimeError(f"history-service returned {r.status_code}")
    submissions = r.json()
    if not submissions:
        return None
    return max(submissions, key=lambda s: s.get("created_at") or "")


def _career_id_from_submission(sub: dict) -> str | None:
    """selected_career (explicit "View Roadmap" click) wins; else the top match.
    Recommendation.id doubles as the roadmap key in this catalog (see careers.json)."""
    if sub.get("selected_career"):
        return sub["selected_career"]
    recs = sub.get("recommendations") or []
    return recs[0]["id"] if recs else None


def _current_career_id(token: str) -> str | None:
    sub = _latest_submission(token)
    return _career_id_from_submission(sub) if sub else None


def get_roadmap_status(*, token: str, **_) -> dict:
    career_id = _current_career_id(token)
    if not career_id:
        return {
            "has_roadmap": False,
            "message": "The user hasn't completed the career assessment yet.",
        }

    progress_r = dapr.invoke(
        "roadmap", f"api/roadmap/{career_id}/progress", headers={"Authorization": token}
    )
    completed = progress_r.json().get("completed_nodes", []) if progress_r.status_code == 200 else []

    roadmap_r = dapr.invoke("roadmap", f"api/roadmap/{career_id}")
    sections = roadmap_r.json().get("sections", []) if roadmap_r.status_code == 200 else []
    all_steps = [n["id"] for s in sections for n in s.get("nodes", [])]
    next_step = next((s for s in all_steps if s not in completed), None)

    return {
        "has_roadmap": True,
        "career_id": career_id,
        "completed_steps": completed,
        "next_step": next_step,
        "total_steps": len(all_steps),
    }


def get_step_details(*, token: str, step_id: str, **_) -> dict:
    career_id = _current_career_id(token)
    if not career_id:
        return {"error": "The user hasn't completed the career assessment yet."}

    roadmap_r = dapr.invoke("roadmap", f"api/roadmap/{career_id}")
    if roadmap_r.status_code != 200:
        raise RuntimeError("roadmap-service unavailable")
    for section in roadmap_r.json().get("sections", []):
        for node in section.get("nodes", []):
            if node.get("id") == step_id:
                return node
    return {"error": f"No step '{step_id}' found in this roadmap."}


def navigate(*, token: str, target: str, step_id: str | None = None, **_) -> dict:
    if target == "questionnaire":
        return {"target": "questionnaire"}
    if target == "roadmap":
        career_id = _current_career_id(token)
        if not career_id:
            return {"error": "No roadmap yet — nothing to navigate to."}
        return {"target": "roadmap", "career_id": career_id, "step_id": step_id}
    return {"error": f"unknown navigate target '{target}'"}


_HANDLERS = {
    "get_roadmap_status": get_roadmap_status,
    "get_step_details": get_step_details,
    "navigate": navigate,
}


def execute(name: str, arguments: dict, *, token: str) -> dict:
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool '{name}'"}
    try:
        return handler(token=token, **arguments)
    except (dapr.DaprError, RuntimeError, TypeError) as exc:
        logger.warning("Tool '%s' failed: %s", name, exc)
        return {"error": f"'{name}' is unavailable right now."}
