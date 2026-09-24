import os
import re
from xml.etree.ElementTree import Element, SubElement, tostring

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, session
from flask_cors import CORS
from psycopg import Connection, connect
from psycopg.rows import dict_row
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "library-login-secret")
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)


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
        }
        return build_response(payload, 200)
    except Exception as exc:
        payload = {
            "service": "library-login-service",
            "status": "error",
            "database": "unavailable",
            "message": str(exc),
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
                cur.execute(
                    """
                    INSERT INTO auth_users (first_name, paternal_last_name, maternal_last_name, email, password_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, first_name, paternal_last_name, maternal_last_name, email
                    """,
                    (first_name, paternal_last_name, maternal_last_name, email, password_hash),
                )
                user = cur.fetchone()
            conn.commit()

        payload = {
            "message": "User registered successfully",
            "user": user,
        }
        return build_response(payload, 201)
    except Exception as exc:
        return build_error(str(exc), 500)


@app.route("/login", methods=["POST"])
def login_user():
    data = request.get_json(silent=True) or request.form or {}
    email = stringify(data.get("email") or "").strip().lower()
    password = stringify(data.get("password") or "")

    if not email or not password:
        return build_error("email and password are required", 400)

    try:
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT id, first_name, paternal_last_name, maternal_last_name, email, password_hash FROM auth_users WHERE email = %s",
                    (email,),
                )
                user = cur.fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            return build_error("Invalid credentials", 401)

        session["user_id"] = user["id"]
        session["first_name"] = user["first_name"]
        session["email"] = user["email"]

        payload = {
            "message": "Login successful",
            "authenticated": True,
            "user": {
                "id": user["id"],
                "first_name": user["first_name"],
                "paternal_last_name": user["paternal_last_name"],
                "maternal_last_name": user["maternal_last_name"],
                "email": user["email"],
            },
        }
        return build_response(payload, 200)
    except Exception as exc:
        return build_error(str(exc), 500)


@app.route("/logout", methods=["POST"])
def logout_user():
    session.clear()
    return build_response({"message": "Session closed successfully", "authenticated": False}, 200)


@app.route("/session", methods=["GET"])
def session_status():
    if "user_id" in session:
        payload = {
            "authenticated": True,
            "user": {
                "id": session.get("user_id"),
                "first_name": session.get("first_name"),
                "email": session.get("email"),
            },
        }
        return build_response(payload, 200)

    return build_response({"authenticated": False}, 200)


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
