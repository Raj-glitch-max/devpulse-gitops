"""
DevPulse — Metrics Service
Exposes Prometheus-style metrics for observability.
Endpoints:
  /metrics  — Prometheus format metrics
  /health   — health check
"""

import os
import time
import random
import logging
from datetime import datetime, timezone
from flask import Flask, Response, jsonify

# ─── Configuration ───────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SERVICE_NAME"] = "metrics-service"
app.config["VERSION"] = os.getenv("APP_VERSION", "1.0.0")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(app.config["SERVICE_NAME"])

# ─── Global Stats (Simulated) ────────────────────────────────────────────────

START_TIME = time.time()

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": app.config["SERVICE_NAME"],
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/metrics", methods=["GET"])
def metrics():
    """
    Simulates Prometheus metrics.
    In a real app, uses prometheus_client library.
    """
    uptime = int(time.time() - START_TIME)
    
    # Simulate some traffic data
    total_reqs = random.randint(1000, 5000)
    error_reqs = random.randint(0, 50)
    cpu_usage = random.uniform(5.0, 45.0)
    mem_usage = (uptime * 1024) % (512 * 1024 * 1024) # simulated growth

    lines = [
        f'# HELP devpulse_uptime_seconds_total Total uptime in seconds',
        f'# TYPE devpulse_uptime_seconds_total counter',
        f'devpulse_uptime_seconds_total {uptime}',
        
        f'# HELP devpulse_http_requests_total Total HTTP requests handled',
        f'# TYPE devpulse_http_requests_total counter',
        f'devpulse_http_requests_total {total_reqs}',
        
        f'# HELP devpulse_http_errors_total Total failed HTTP requests',
        f'# TYPE devpulse_http_errors_total counter',
        f'devpulse_http_errors_total {error_reqs}',
        
        f'# HELP devpulse_cpu_usage_percent Current CPU usage percentage',
        f'# TYPE devpulse_cpu_usage_percent gauge',
        f'devpulse_cpu_usage_percent {cpu_usage:.2f}',
        
        f'# HELP devpulse_memory_bytes Current memory usage in bytes',
        f'# TYPE devpulse_memory_bytes gauge',
        f'devpulse_memory_bytes {mem_usage}',
    ]
    
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5005"))
    log.info("Starting %s on port %d", app.config["SERVICE_NAME"], port)
    app.run(host="0.0.0.0", port=port)
