"""
DevPulse — API Gateway (V2)
Adds JWT validation and Rate Limiting.
Routes requests to downstream services.
"""

import os
import logging
import time
from datetime import datetime, timezone
from collections import deque

import requests
import jwt # pyjwt
from flask import Flask, jsonify, request, Response

# ─── Configuration ───────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SERVICE_NAME"] = "api-gateway"
app.config["VERSION"] = os.getenv("APP_VERSION", "2.0.0")

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:5001")
TASK_SERVICE_URL = os.getenv("TASK_SERVICE_URL", "http://task-service:5002")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:5003")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:5004")
METRICS_SERVICE_URL = os.getenv("METRICS_SERVICE_URL", "http://metrics-service:5005")

# Security
JWT_SECRET = os.getenv("JWT_SECRET", "devpulse-super-secret-key")
JWT_ALGO = "HS256"

# Rate Limiting: 100 requests per minute per IP
RATE_LIMIT_MAX = 100
RATE_LIMIT_WINDOW = 60 # seconds
ip_trackers = {} # ip -> deque of timestamps

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(app.config["SERVICE_NAME"])

SERVICES = {
    "user-service": USER_SERVICE_URL,
    "task-service": TASK_SERVICE_URL,
    "notification-service": NOTIFICATION_SERVICE_URL,
    "auth-service": AUTH_SERVICE_URL,
    "metrics-service": METRICS_SERVICE_URL,
}

# ─── Rate Limiter ────────────────────────────────────────────────────────────

def _check_rate_limit():
    ip = request.remote_addr
    now = time.time()
    if ip not in ip_trackers:
        ip_trackers[ip] = deque()
    
    tracker = ip_trackers[ip]
    while tracker and tracker[0] < now - RATE_LIMIT_WINDOW:
        tracker.popleft()
    
    if len(tracker) >= RATE_LIMIT_MAX:
        log.warning("Rate limit exceeded for IP: %s", ip)
        return False
    
    tracker.append(now)
    return True

# ─── Auth Middleware ─────────────────────────────────────────────────────────

def _validate_auth():
    """Verify JWT token for protected routes."""
    # Allow /login, /health, /metrics without token
    if request.path in ["/", "/health", "/metrics", "/auth/login"]:
        return True

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        log.warning("Missing or invalid Authorization header for %s", request.path)
        return False
    
    token = auth_header.split(" ")[1]
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return True
    except Exception as e:
        log.warning("JWT Validation failed: %s", e)
        return False

# ─── Proxy Helper ────────────────────────────────────────────────────────────

def _proxy(upstream_url: str, path: str) -> Response:
    if not _check_rate_limit():
        return jsonify({"status": "error", "message": "Too many requests"}), 429
    
    if not _validate_auth():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    url = f"{upstream_url}{path}"
    method = request.method
    headers = {k: v for k, v in request.headers if k.lower() not in ("host", "connection", "content-length")}
    headers["X-Forwarded-By"] = "api-gateway"

    try:
        resp = requests.request(method=method, url=url, headers=headers, params=request.args, 
                               data=request.get_data(), timeout=10)
        excluded_headers = {"content-encoding", "content-length", "transfer-encoding", "connection"}
        response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}
        return Response(resp.content, status=resp.status_code, headers=response_headers)
    except Exception as exc:
        log.error("Proxy error: %s", exc)
        return jsonify({"status": "error", "message": "Upstream service unreachable"}), 502

# ─── Health Check ────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    results = {}
    for name, url in SERVICES.items():
        try:
            r = requests.get(f"{url}/health", timeout=2)
            results[name] = r.json().get("status", "unknown")
        except:
            results[name] = "unreachable"
            
    all_ok = all(s == "healthy" for s in results.values())
    return jsonify({
        "status": "healthy" if all_ok else "degraded",
        "downstream": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200 if all_ok else 503

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def root(): return root_info()

@app.route("/auth/login", methods=["POST"])
def login_proxy(): return _proxy(AUTH_SERVICE_URL, "/login")

@app.route("/users", methods=["GET", "POST"])
@app.route("/users/<path:p>", methods=["GET", "POST", "PUT", "DELETE"])
def user_proxy(p=""): return _proxy(USER_SERVICE_URL, f"/users/{p}" if p else "/users")

@app.route("/tasks", methods=["GET", "POST"])
@app.route("/tasks/<path:p>", methods=["GET", "POST", "PUT", "DELETE"])
def task_proxy(p=""): return _proxy(TASK_SERVICE_URL, f"/tasks/{p}" if p else "/tasks")

@app.route("/notifications", methods=["GET", "POST"])
@app.route("/notifications/<path:p>", methods=["GET", "POST", "PUT", "DELETE"])
def notif_proxy(p=""): return _proxy(NOTIFICATION_SERVICE_URL, f"/notifications/{p}" if p else "/notifications")

@app.route("/metrics", methods=["GET"])
def metrics_proxy(): return _proxy(METRICS_SERVICE_URL, "/metrics")


def root_info():
    return jsonify({
        "service": "devpulse-api-gateway",
        "version": app.config["VERSION"],
        "routes": ["/health", "/metrics", "/auth/login", "/users", "/tasks", "/notifications"]
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    log.info("Starting %s V2 on port %d", app.config["SERVICE_NAME"], port)
    app.run(host="0.0.0.0", port=port)
