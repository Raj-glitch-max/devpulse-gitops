"""
DevPulse — Auth Service
Handles identity and JWT issuance.
Endpoints:
  POST /login   — returns a JWT
  GET  /health  — health check
"""

import os
import logging
import time
from datetime import datetime, timezone, timedelta
import jwt  # pyjwt
from flask import Flask, jsonify, request

# ─── Configuration ───────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SERVICE_NAME"] = "auth-service"
app.config["VERSION"] = os.getenv("APP_VERSION", "1.0.0")

# SECURITY: This would normally come from a K8s Secret
JWT_SECRET = os.getenv("JWT_SECRET", "devpulse-super-secret-key")
JWT_ALGO = "HS256"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(app.config["SERVICE_NAME"])

# ─── Mock User Database ──────────────────────────────────────────────────────
# In a real app, this would verify against user-service + password hash
CREDENTIALS = {
    "admin@devpulse.io": "password123",
    "alice@devpulse.io": "password123",
    "raj@devpulse.io": "password123",
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _ok(data, status=200):
    return jsonify({"status": "success", "data": data}), status


def _error(message, status=400):
    return jsonify({"status": "error", "message": message}), status


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": app.config["SERVICE_NAME"],
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return _error("JSON body required")

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return _error("Email and password required")

    # Simple verify
    if CREDENTIALS.get(email) != password:
        log.warning("Failed login attempt for: %s", email)
        return _error("Invalid credentials", 401)

    # Generate JWT
    payload = {
        "sub": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "role": "admin" if email == "admin@devpulse.io" else "user"
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    log.info("Successful login for: %s", email)
    return _ok({"token": token})


@app.route("/validate", methods=["POST"])
def validate():
    """Internal endpoint for other services to validate tokens."""
    data = request.get_json(silent=True)
    token = data.get("token") if data else None

    if not token:
        return _error("No token provided", 400)

    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return _ok(decoded)
    except jwt.ExpiredSignatureError:
        return _error("Token expired", 401)
    except jwt.InvalidTokenError:
        return _error("Invalid token", 401)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5004"))
    log.info("Starting %s on port %d", app.config["SERVICE_NAME"], port)
    app.run(host="0.0.0.0", port=port)
