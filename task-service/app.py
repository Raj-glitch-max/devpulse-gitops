"""
DevPulse — Task Service
Manages engineering tasks with assignee validation against user-service.
Endpoints:
  GET  /tasks   — list all tasks
  POST /tasks   — create a task (expects JSON: {"title": "...", "assignee_id": "..."})
  GET  /tasks/<id> — get a single task
  GET  /health  — health check
"""

import os
import uuid
import logging
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request

# ─── Configuration ───────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SERVICE_NAME"] = "task-service"
app.config["VERSION"] = os.getenv("APP_VERSION", "1.0.0")

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:5001")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(app.config["SERVICE_NAME"])

# ─── In-Memory Data Store ────────────────────────────────────────────────────

TASKS: dict[str, dict] = {}

# Seed tasks
_SEED = [
    {"title": "Set up CI/CD pipeline", "description": "Configure GitHub Actions for automated testing and deployment", "priority": "high"},
    {"title": "Write API documentation", "description": "Document all REST endpoints with examples", "priority": "medium"},
    {"title": "Fix login timeout bug", "description": "Users report session expires too early", "priority": "high"},
]

for _t in _SEED:
    _id = str(uuid.uuid4())
    TASKS[_id] = {
        "id": _id,
        "title": _t["title"],
        "description": _t["description"],
        "priority": _t.get("priority", "medium"),
        "status": "open",
        "assignee_id": None,
        "assignee_name": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _ok(data, status=200):
    return jsonify({"status": "success", "data": data}), status


def _error(message, status=400):
    return jsonify({"status": "error", "message": message}), status


def _validate_assignee(user_id: str) -> dict | None:
    """Call user-service to check if the assignee exists. Returns user dict or None."""
    try:
        resp = requests.get(f"{USER_SERVICE_URL}/users/{user_id}", timeout=5)
        if resp.status_code == 200:
            body = resp.json()
            return body.get("data")
        log.warning("User-service returned %d for user %s", resp.status_code, user_id)
        return None
    except requests.RequestException as exc:
        log.error("Cannot reach user-service: %s", exc)
        return None


def _check_user_service_health() -> bool:
    try:
        resp = requests.get(f"{USER_SERVICE_URL}/health", timeout=3)
        return resp.status_code == 200
    except requests.RequestException:
        return False


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    user_svc_up = _check_user_service_health()
    overall = "healthy" if user_svc_up else "degraded"
    return jsonify({
        "service": app.config["SERVICE_NAME"],
        "status": overall,
        "version": app.config["VERSION"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "user-service": "up" if user_svc_up else "down",
        },
        "task_count": len(TASKS),
    }), 200 if user_svc_up else 503


@app.route("/tasks", methods=["GET"])
def list_tasks():
    log.info("Listing all tasks — count=%d", len(TASKS))
    return _ok(list(TASKS.values()))


@app.route("/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    task = TASKS.get(task_id)
    if not task:
        return _error("Task not found", 404)
    return _ok(task)


@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True)
    if not data:
        return _error("Request body must be JSON")

    title = data.get("title", "").strip()
    if not title:
        return _error("Field 'title' is required")

    description = data.get("description", "").strip()
    priority = data.get("priority", "medium").strip()
    assignee_id = data.get("assignee_id", "").strip() or None
    assignee_name = None

    # Validate assignee exists in user-service
    if assignee_id:
        user = _validate_assignee(assignee_id)
        if not user:
            return _error(f"Assignee '{assignee_id}' not found in user-service. "
                          "Make sure user-service is running and the user exists.", 422)
        assignee_name = user.get("name")

    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "title": title,
        "description": description,
        "priority": priority,
        "status": "open",
        "assignee_id": assignee_id,
        "assignee_name": assignee_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    TASKS[task_id] = task
    log.info("Created task: %s (%s) → assignee=%s", title, task_id, assignee_name)
    return _ok(task, 201)


# ─── Entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5002"))
    log.info("Starting %s on port %d", app.config["SERVICE_NAME"], port)
    app.run(host="0.0.0.0", port=port)
