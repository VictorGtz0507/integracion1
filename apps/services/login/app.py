import os
import re
import hashlib
import json
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

import jwt
import redis
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, session
from flask_cors import CORS
from flask_session import Session
from psycopg import Connection, connect
from psycopg.rows import dict_row
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.redis_support import RedisUnavailable, get_redis, metrics_snapshot, require_redis, timed_redis_call

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
ACCESS_TOKEN_TTL_SECONDS = 1200
REFRESH_TOKEN_TTL_SECONDS = int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", "604800"))
app.config.update(
    SESSION_TYPE="redis",
    SESSION_REDIS=get_redis(),
    SESSION_KEY_PREFIX="login:session:",
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=timedelta(seconds=int(os.getenv("SESSION_TTL_SECONDS", "604800"))),
    SESSION_USE_SIGNER=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
    APP_ENV=os.getenv("APP_ENV", "development").lower(),
)
Session(app)
if app.config["APP_ENV"] == "production" and not os.getenv("CORS_ORIGINS"):
    raise RuntimeError("CORS_ORIGINS must be configured in production")
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                origin.strip()
                for origin in os.getenv(
                    "CORS_ORIGINS",
                    "http://localhost:3000,http://127.0.0.1:3000",
                ).split(",")
                if origin.strip()
            ]
        }
    },
    supports_credentials=True,
)


def create_token(user_payload):
    if not app.config["JWT_SECRET_KEY"]:
        raise RuntimeError("JWT_SECRET_KEY is required")
    now = datetime.now(timezone.utc)
    token_id = secrets.token_urlsafe(24)
    payload = {
        "sub": str(user_payload["id"]),
        "user_id": int(user_payload["id"]),
        "role_id": int(user_payload["role_id"]),
        "role": user_payload["role"],
        "email": user_payload["email"],
        "first_name": user_payload["first_name"],
        "jti": token_id,
        "exp": now + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS),
        "iat": now,
    }
    return jwt.encode(payload, app.config["JWT_SECRET_KEY"], algorithm="HS256"), token_id


def refresh_key(token):
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"jwt:refresh:{digest}"


def save_refresh_token(client, token, user, token_id):
    timed_redis_call(
        "auth.refresh_store",
        client.setex,
        refresh_key(token),
        REFRESH_TOKEN_TTL_SECONDS,
        json.dumps({"user": user, "jti": token_id}),
    )


def redis_failure_response():
    return build_error("Authentication storage is temporarily unavailable", 503)


def get_db_config():
    return {
        "dbname": os.getenv("DB_NAME", "library_db"),
        "user": os.getenv("DB_USER", "library_user"),
        "password": os.getenv("DB_PASSWORD", "666"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "connect_timeout": 5,
    }


def get_connection() -> Connection:
    return connect(**get_db_config())


def ensure_schema() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS roles (
                    role_id SERIAL PRIMARY KEY,
                    role_name VARCHAR(50) NOT NULL UNIQUE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_users (
                    id SERIAL PRIMARY KEY,
                    first_name VARCHAR(100) NOT NULL,
                    paternal_last_name VARCHAR(100) NOT NULL,
                    maternal_last_name VARCHAR(100) NOT NULL DEFAULT '',
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute("INSERT INTO roles (role_name) VALUES ('admin'), ('staff'), ('customer') ON CONFLICT (role_name) DO NOTHING")
            cur.execute("ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS role_id INTEGER REFERENCES roles(role_id)")
            cur.execute(
                """
                UPDATE auth_users
                SET role_id = (SELECT role_id FROM roles WHERE role_name = 'customer')
                WHERE role_id IS NULL
                """
            )
            cur.execute("ALTER TABLE auth_users ALTER COLUMN role_id SET NOT NULL")
        conn.commit()


EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_format() -> str:
    fmt = (request.args.get("format") or "xml").lower()
    return fmt if fmt in {"xml", "json"} else "xml"


def stringify(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def append_xml(parent, value):
    if isinstance(value, dict):
        for key, item in value.items():
            child = SubElement(parent, str(key))
            append_xml(child, item)
        return

    if isinstance(value, list):
        for item in value:
            entry = SubElement(parent, "item")
            append_xml(entry, item)
        return

    parent.text = stringify(value)


def build_xml_response(data, root_name="response"):
    root = Element(root_name)
    append_xml(root, data)
    return Response(tostring(root, encoding="utf-8", xml_declaration=True), mimetype="application/xml")


def build_response(payload, status_code=200):
    fmt = normalize_format()
    if fmt == "json":
        return jsonify(payload), status_code

    xml_payload = {"status": status_code, "data": payload}
    return build_xml_response(xml_payload), status_code


def build_error(message, status_code=400):
    fmt = normalize_format()
    if fmt == "json":
        return jsonify({"error": message}), status_code

    return build_xml_response({"error": message}), status_code


@app.route("/health", methods=["GET"])
def health():
    redis_connected = False
    try:
        require_redis()
        redis_connected = True
    except RedisUnavailable:
        pass
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                result = cur.fetchone()

        payload = {
            "service": "library-login-service",
            "status": "ok",
            "database": "connected" if result else "unavailable",
            "database_name": os.getenv("DB_NAME", "library_db"),
            "redis": "connected" if redis_connected else "unavailable",
        }
        return build_response(payload, 200 if redis_connected else 503)
    except Exception:
        payload = {
            "service": "library-login-service",
            "status": "error",
            "database": "unavailable",
            "redis": "connected" if redis_connected else "unavailable",
            "message": "A required dependency is unavailable",
        }
        return build_response(payload, 500)


@app.route("/register", methods=["POST"])
def register_user():
    data = request.get_json(silent=True) or request.form or {}

    first_name = stringify(data.get("first_name") or data.get("nombre") or "").strip()
    paternal_last_name = stringify(data.get("paternal_last_name") or data.get("apellido_paterno") or "").strip()
    maternal_last_name = stringify(data.get("maternal_last_name") or data.get("apellido_materno") or "").strip()
    email = stringify(data.get("email") or "").strip().lower()
    password = stringify(data.get("password") or "")

    if not all([first_name, paternal_last_name, email, password]):
        return build_error("first_name, paternal_last_name, email and password are required", 400)

    if not EMAIL_REGEX.match(email):
        return build_error("Invalid email format", 400)

    try:
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT id FROM auth_users WHERE email = %s", (email,))
                existing = cur.fetchone()
                if existing:
                    return build_error("Email already registered", 409)

                password_hash = generate_password_hash(password)
                cur.execute("SELECT role_id FROM roles WHERE role_name = 'customer'")
                customer_role = cur.fetchone()
                cur.execute(
                    """
                    INSERT INTO auth_users (first_name, paternal_last_name, maternal_last_name, email, password_hash, role_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, first_name, paternal_last_name, maternal_last_name, email, role_id
                    """,
                    (first_name, paternal_last_name, maternal_last_name, email, password_hash, customer_role["role_id"]),
                )
                user = cur.fetchone()
            conn.commit()

        payload = {
            "message": "User registered successfully",
            "user": user,
        }
        return build_response(payload, 201)
    except Exception:
        return build_error("Registration could not be completed", 500)


@app.route("/login", methods=["POST"])
def login_user():
    data = request.get_json(silent=True) or request.form or {}
    email = stringify(data.get("email") or "").strip().lower()
    password = stringify(data.get("password") or "")

    if not email or not password:
        return build_error("email and password are required", 400)

    try:
        client = require_redis()
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                          """
                          SELECT u.id, u.first_name, u.paternal_last_name, u.maternal_last_name,
                              u.email, u.password_hash, u.role_id, r.role_name AS role
                          FROM auth_users u JOIN roles r ON r.role_id = u.role_id
                          WHERE u.email = %s
                          """,
                    (email,),
                )
                user = cur.fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            return build_error("Invalid credentials", 401)

        public_user = {
            "id": user["id"],
            "email": user["email"],
            "first_name": user["first_name"],
            "role_id": user["role_id"],
            "role": user["role"],
        }
        token, token_id = create_token(public_user)
        refresh_token = secrets.token_urlsafe(48)
        save_refresh_token(client, refresh_token, public_user, token_id)
        session.permanent = True
        session["user_id"] = user["id"]
        session["first_name"] = user["first_name"]
        session["email"] = user["email"]
        session["role_id"] = user["role_id"]
        session["role"] = user["role"]
        session["refresh_key"] = refresh_key(refresh_token)
        session["access_jti"] = token_id
        session["access_exp"] = int(datetime.now(timezone.utc).timestamp()) + ACCESS_TOKEN_TTL_SECONDS

        payload = {
            "message": "Login successful",
            "authenticated": True,
            "token": token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS,
            "refresh_token": refresh_token,
            "refresh_expires_in": REFRESH_TOKEN_TTL_SECONDS,
            "user": {
                "id": user["id"],
                "first_name": user["first_name"],
                "paternal_last_name": user["paternal_last_name"],
                "maternal_last_name": user["maternal_last_name"],
                "email": user["email"],
                "role_id": user["role_id"],
                "role": user["role"],
            },
        }
        return build_response(payload, 200)
    except (RedisUnavailable, redis.RedisError):
        return redis_failure_response()
    except Exception:
        return build_error("Login could not be completed", 500)


@app.route("/logout", methods=["POST"])
def logout_user():
    try:
        client = require_redis()
        data = request.get_json(silent=True) or request.form or {}
        refresh_token_keys = {session.get("refresh_key")} - {None}
        submitted_refresh_token = stringify(data.get("refresh_token") or "")
        if submitted_refresh_token:
            refresh_token_keys.add(refresh_key(submitted_refresh_token))
        token_ids = {session.get("access_jti")} - {None}
        for refresh_token_key in refresh_token_keys:
            refresh_payload = timed_redis_call("auth.refresh_read_for_logout", client.get, refresh_token_key)
            if refresh_payload:
                token_ids.add(json.loads(refresh_payload).get("jti"))
        token_ids.discard(None)
        token_expiry = int(session.get("access_exp", 0))
        for token_id in token_ids:
            now = int(datetime.now(timezone.utc).timestamp())
            ttl = token_expiry - now if token_id == session.get("access_jti") else ACCESS_TOKEN_TTL_SECONDS
            if ttl > 0:
                timed_redis_call(
                    "auth.jwt_revoke",
                    client.setex,
                    f"jwt:revoked:{token_id}",
                    ttl,
                    "1",
                )
        if refresh_token_keys:
            timed_redis_call(
                "auth.refresh_delete",
                client.delete,
                *refresh_token_keys,
            )
        session.clear()
        return build_response({"message": "Session closed successfully", "authenticated": False}, 200)
    except RedisUnavailable:
        return redis_failure_response()
    except Exception:
        return redis_failure_response()


@app.route("/refresh", methods=["POST"])
def refresh_access_token():
    data = request.get_json(silent=True) or request.form or {}
    old_refresh_token = stringify(data.get("refresh_token") or "")
    if not old_refresh_token:
        return build_error("refresh_token is required", 400)

    try:
        client = require_redis()
        old_key = refresh_key(old_refresh_token)
        refresh_data = timed_redis_call("auth.refresh_consume", client.getdel, old_key)
        if not refresh_data:
            return build_error("Invalid or expired refresh token", 401)

        refresh_payload = json.loads(refresh_data)
        user = refresh_payload["user"]
        previous_jti = refresh_payload.get("jti")
        if previous_jti:
            timed_redis_call(
                "auth.jwt_revoke",
                client.setex,
                f"jwt:revoked:{previous_jti}",
                ACCESS_TOKEN_TTL_SECONDS,
                "1",
            )
        token, token_id = create_token(user)
        new_refresh_token = secrets.token_urlsafe(48)
        save_refresh_token(client, new_refresh_token, user, token_id)

        if session.get("refresh_key") == old_key:
            session["refresh_key"] = refresh_key(new_refresh_token)
            session["access_jti"] = token_id
            session["access_exp"] = int(datetime.now(timezone.utc).timestamp()) + ACCESS_TOKEN_TTL_SECONDS

        return build_response({
            "authenticated": True,
            "token": token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS,
            "refresh_token": new_refresh_token,
            "refresh_expires_in": REFRESH_TOKEN_TTL_SECONDS,
        }, 200)
    except (RedisUnavailable, redis.RedisError):
        return redis_failure_response()
    except Exception:
        return redis_failure_response()


@app.route("/session", methods=["GET"])
def session_status():
    try:
        require_redis()
        if "user_id" in session:
            payload = {
                "authenticated": True,
                "user": {
                    "id": session.get("user_id"),
                    "first_name": session.get("first_name"),
                    "email": session.get("email"),
                    "role_id": session.get("role_id"),
                    "role": session.get("role"),
                },
            }
            return build_response(payload, 200)
    except (RedisUnavailable, redis.RedisError):
        return redis_failure_response()

    return build_response({"authenticated": False}, 200)


@app.route("/metrics", methods=["GET"])
def metrics():
    return jsonify(metrics_snapshot())


OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Library Login API",
        "version": "1.0.0",
        "description": "Authentication microservice for the online library platform.",
    },
    "servers": [{"url": "http://localhost:5000"}],
    "paths": {
        "/register": {
            "post": {
                "summary": "Register a new user",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["first_name", "paternal_last_name", "email", "password"],
                                "properties": {
                                    "first_name": {"type": "string"},
                                    "paternal_last_name": {"type": "string"},
                                    "maternal_last_name": {"type": "string"},
                                    "email": {"type": "string", "format": "email"},
                                    "password": {"type": "string", "format": "password"},
                                },
                            }
                        }
                    }
                },
                "responses": {
                    "201": {"description": "User created successfully"},
                    "400": {"description": "Bad request"},
                    "409": {"description": "Email already exists"},
                },
            }
        },
        "/login": {
            "post": {
                "summary": "Authenticate user and create a Flask session",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["email", "password"],
                                "properties": {
                                    "email": {"type": "string", "format": "email"},
                                    "password": {"type": "string", "format": "password"},
                                },
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Login successful"},
                    "401": {"description": "Invalid credentials"},
                },
            }
        },
        "/logout": {
            "post": {
                "summary": "Terminate the current user session",
                "responses": {"200": {"description": "Session closed"}},
            }
        },
        "/refresh": {
            "post": {
                "summary": "Rotate a refresh token and issue a 20-minute access JWT",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["refresh_token"],
                                "properties": {"refresh_token": {"type": "string"}},
                            }
                        }
                    },
                },
                "responses": {
                    "200": {"description": "New access and refresh tokens issued"},
                    "401": {"description": "Invalid or expired refresh token"},
                    "503": {"description": "Redis authentication store unavailable"},
                },
            }
        },
        "/session": {
            "get": {
                "summary": "Check if a session exists for the current user",
                "responses": {"200": {"description": "Current session state"}},
            }
        },
        "/health": {
            "get": {
                "summary": "Check the health of the service and PostgreSQL",
                "responses": {"200": {"description": "Service healthy"}},
            }
        },
    },
}


@app.route("/swagger.json", methods=["GET"])
def swagger_json():
    return jsonify(OPENAPI_SPEC)


@app.route("/swagger.xml", methods=["GET"])
def swagger_xml():
    return build_xml_response({"swagger": OPENAPI_SPEC}), 200


@app.route("/docs", methods=["GET"])
def docs_page():
    return """
    <html>
      <body>
        <h2>Library Login Service</h2>
        <p>Swagger JSON: <a href="/swagger.json">/swagger.json</a></p>
        <p>Swagger XML: <a href="/swagger.xml">/swagger.xml</a></p>
      </body>
    </html>
    """


if __name__ == "__main__":
    try:
        ensure_schema()
    except Exception as exc:
        print(f"Database init warning: {exc}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
