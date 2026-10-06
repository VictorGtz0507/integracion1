import os
from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS
from psycopg import connect

from shared.redis_support import metrics_snapshot


def create_service(name):
    app = Flask(name)
    configured_origins = os.getenv("CORS_ORIGINS")
    if not configured_origins and os.getenv("APP_ENV", "development").lower() == "production":
        raise RuntimeError("CORS_ORIGINS must be configured in production")
    origins = [
        origin.strip()
        for origin in (configured_origins or "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if origin.strip()
    ]
    CORS(app, resources={r"/*": {"origins": origins}})

    @app.get("/health")
    def health():
        try:
            with get_db_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
            redis_state = metrics_snapshot().get("redis", {}).get("connected", False)
            return jsonify({
                "service": name,
                "database": "connected",
                "redis": "connected" if redis_state else "unavailable",
            }), (200 if redis_state else 503)
        except Exception:
            return jsonify({"service": name, "database": "unavailable"}), 503

    @app.get("/metrics")
    def metrics():
        return jsonify(metrics_snapshot())

    return app


def get_db_connection():
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return connect(dsn, connect_timeout=5)
    return connect(
        dbname=os.getenv("DB_NAME", "library_db"),
        user=os.getenv("DB_USER", "library_user"),
        password=os.getenv("DB_PASSWORD", "666"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        connect_timeout=5,
    )


def ensure_library_schema():
    schema_path = Path(__file__).resolve().parents[1] / "schema.sql"
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            for statement in schema_path.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    cursor.execute(statement)
        connection.commit()