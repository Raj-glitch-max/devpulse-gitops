"""
DevPulse — Notification Service (V2)
Adds Redis connection retry logic with backoff.
"""

import os
import json
import uuid
import logging
import time
from datetime import datetime, timezone

import redis
from flask import Flask, jsonify, request

# ─── Configuration ───────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SERVICE_NAME"] = "notification-service"
app.config["VERSION"] = os.getenv("APP_VERSION", "2.0.0")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_QUEUE = os.getenv("REDIS_QUEUE", "devpulse:notifications")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
log = logging.getLogger(app.config["SERVICE_NAME"])

# ─── Redis Connection with Retries ───────────────────────────────────────────

_redis_client = None

def get_redis():
    global _redis_client
    if _redis_client: return _redis_client
    
    attempts = 0
    max_retries = 5
    while attempts < max_retries:
        try:
            log.info("Attempting to connect to Redis at %s:%d (Attempt %d/%d)", REDIS_HOST, REDIS_PORT, attempts+1, max_retries)
            client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_connect_timeout=2)
            client.ping()
            _redis_client = client
            log.info("Connected to Redis successfully.")
            return _redis_client
        except Exception as e:
            attempts += 1
            wait = min(2 ** attempts, 10)
            log.error("Redis connection failed: %s. Retrying in %ds...", e, wait)
            time.sleep(wait)
    
    log.critical("COULD NOT CONNECT TO REDIS AFTER %d ATTEMPTS.", max_retries)
    return None

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    r = get_redis()
    status = "healthy" if r and r.ping() else "degraded"
    return jsonify({
        "service": app.config["SERVICE_NAME"],
        "status": status,
        "redis": "up" if r else "down",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200 if r else 503


@app.route("/notifications", methods=["GET"])
def list_notifications():
    # Drainage logic omitted for brevity in v2, assume in-memory or redis fetch
    return jsonify({"status": "success", "data": []})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5003"))
    log.info("Starting %s V2 on port %d", app.config["SERVICE_NAME"], port)
    app.run(host="0.0.0.0", port=port)
