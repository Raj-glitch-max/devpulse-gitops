"""
DevPulse — User Service (V2 - Persistent)
Manages users. Connects to PostgreSQL.
Falls back to in-memory if DB is unreachable to allow development survival.
"""

import os
import uuid
import logging
import time
from datetime import datetime, timezone

import psycopg2  # for postgres
from flask import Flask, jsonify, request, abort

# ─── Configuration ───────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SERVICE_NAME"] = "user-service"
app.config["VERSION"] = os.getenv("APP_VERSION", "2.0.0")

# DB Config
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_NAME = os.getenv("POSTGRES_DB", "devpulse")
DB_USER = os.getenv("POSTGRES_USER", "admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "password")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(app.config["SERVICE_NAME"])

# ─── Database Initialization ──────────────────────────────────────────────────

db_conn = None

def get_db():
    global db_conn
    if db_conn is None or db_conn.closed:
        try:
            db_conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                port=DB_PORT,
                connect_timeout=5
            )
            log.info("Successfully connected to PostgreSQL at %s", DB_HOST)
            # Initialize table
            with db_conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id UUID PRIMARY KEY,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        role TEXT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                db_conn.commit()
        except Exception as e:
            log.error("Failed to connect to PostgreSQL: %s. Using in-memory fallback.", e)
            return None
    return db_conn

# ─── In-Memory Fallback (For when DB is stuck in 'Pain Phase') ────────────────

MEM_USERS: dict[str, dict] = {}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _ok(data, status=200):
    return jsonify({"status": "success", "data": data}), status


def _error(message, status=400):
    return jsonify({"status": "error", "message": message}), status


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    conn = get_db()
    db_status = "up" if conn and not conn.closed else "down"
    return jsonify({
        "service": app.config["SERVICE_NAME"],
        "status": "healthy" if db_status == "up" else "degraded",
        "version": app.config["VERSION"],
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/users", methods=["GET"])
def list_users():
    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, email, role, created_at FROM users")
                rows = cur.fetchall()
                results = []
                for r in rows:
                    results.append({
                        "id": str(r[0]), "name": r[1], "email": r[2], 
                        "role": r[3], "created_at": r[4].isoformat()
                    })
                return _ok(results)
        except Exception as e:
            log.error("DB Query failed: %s", e)
    
    log.info("Returning results from in-memory fallback")
    return _ok(list(MEM_USERS.values()))


@app.route("/users/<user_id>", methods=["GET"])
def get_user(user_id):
    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, email, role, created_at FROM users WHERE id = %s", (user_id,))
                r = cur.fetchone()
                if r:
                    return _ok({
                        "id": str(r[0]), "name": r[1], "email": r[2], 
                        "role": r[3], "created_at": r[4].isoformat()
                    })
        except Exception as e:
            log.error("DB Query failed: %s", e)
    
    user = MEM_USERS.get(user_id)
    if not user:
        return _error("User not found", 404)
    return _ok(user)


@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    if not data: return _error("JSON body required")

    uid = str(uuid.uuid4())
    name = data.get("name")
    email = data.get("email")
    role = data.get("role", "engineer")

    if not name or not email:
        return _error("Name and Email required")

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (id, name, email, role) VALUES (%s, %s, %s, %s) RETURNING created_at",
                    (uid, name, email, role)
                )
                ts = cur.fetchone()[0]
                conn.commit()
                return _ok({"id": uid, "name": name, "email": email, "role": role, "created_at": ts.isoformat()}, 201)
        except psycopg2.IntegrityError:
            conn.rollback()
            return _error("Email already exists", 409)
        except Exception as e:
            log.error("DB Insert failed: %s", e)
            conn.rollback()

    # Fallback
    user = {"id": uid, "name": name, "email": email, "role": role, "created_at": datetime.now(timezone.utc).isoformat()}
    MEM_USERS[uid] = user
    return _ok(user, 201)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    log.info("Starting %s V2 on port %d", app.config["SERVICE_NAME"], port)
    app.run(host="0.0.0.0", port=port)
