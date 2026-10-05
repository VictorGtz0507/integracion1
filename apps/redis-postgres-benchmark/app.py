import json
import os
import statistics
import time
from datetime import date, datetime
from decimal import Decimal

import redis
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from psycopg import connect
from psycopg.rows import dict_row

load_dotenv()

app = Flask(__name__)

REDIS_KEY = os.getenv("REDIS_CATALOG_KEY", "library-benchmark:catalog:v1")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))

CATALOG_SQL = """
    SELECT
        b.id,
        b.title,
        b.isbn,
        b.description,
        b.price_cents,
        b.stock,
        b.published_year,
        COALESCE((
            SELECT json_agg(a.name ORDER BY a.name)
            FROM authors a
            JOIN book_authors ba ON ba.author_id = a.id
            WHERE ba.book_id = b.id
        ), '[]'::json) AS authors,
        COALESCE((
            SELECT json_agg(c.name ORDER BY c.name)
            FROM categories c
            JOIN book_categories bc ON bc.category_id = c.id
            WHERE bc.book_id = b.id
        ), '[]'::json) AS categories,
        COALESCE((
            SELECT json_agg(json_build_object('term', co.term, 'definition', co.definition) ORDER BY co.term)
            FROM concepts co
            WHERE co.book_id = b.id
        ), '[]'::json) AS concepts,
        COALESCE((
            SELECT json_agg(json_build_object(
                'id', i.id,
                'filename', i.filename,
                'original_name', i.original_name,
                'mime_type', i.mime_type
            ) ORDER BY i.id)
            FROM images i
            WHERE i.book_id = b.id
        ), '[]'::json) AS images
    FROM books b
    ORDER BY b.id
"""


def postgres_connection():
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


def redis_client():
    return redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        socket_connect_timeout=3,
        socket_timeout=5,
        decode_responses=True,
    )


def json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Cannot encode {type(value).__name__} as JSON")


def catalog_json(books):
    return json.dumps(books, ensure_ascii=False, separators=(",", ":"), default=json_default)


def normalize_value(value):
    if isinstance(value, dict):
        return {key: normalize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def query_catalog():
    with postgres_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(CATALOG_SQL)
            return [normalize_value(dict(row)) for row in cursor.fetchall()]


def get_catalog_cached(client=None):
    client = client or redis_client()
    cached = client.get(REDIS_KEY)
    if cached is not None:
        return json.loads(cached), True

    books = query_catalog()
    client.setex(REDIS_KEY, CACHE_TTL_SECONDS, catalog_json(books))
    return books, False


def percentile(values, fraction):
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.5)))
    return ordered[index]


def summarize_timings(timings_ms):
    return {
        "average_ms": round(statistics.mean(timings_ms), 3),
        "median_ms": round(statistics.median(timings_ms), 3),
        "p95_ms": round(percentile(timings_ms, 0.95), 3),
        "min_ms": round(min(timings_ms), 3),
        "max_ms": round(max(timings_ms), 3),
        "operations_per_second": round(1000 / statistics.mean(timings_ms), 2)
        if statistics.mean(timings_ms) > 0
        else 0,
    }


def measure(operation, iterations):
    timings = []
    result = None
    for _ in range(iterations):
        started = time.perf_counter_ns()
        result = operation()
        timings.append((time.perf_counter_ns() - started) / 1_000_000)
    return summarize_timings(timings), result


def capacity_snapshot():
    result = {"postgres": None, "redis": None, "errors": []}
    try:
        with postgres_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), pg_database_size(current_database()), (SELECT COUNT(*) FROM books)")
                database_name, database_bytes, book_count = cursor.fetchone()
        result["postgres"] = {
            "connected": True,
            "database": database_name,
            "database_bytes": database_bytes,
            "database_mb": round(database_bytes / (1024 * 1024), 3),
            "book_count": book_count,
        }
    except Exception:
        result["errors"].append("PostgreSQL no responde. Revisa DB_HOST, credenciales y acceso de red.")

    try:
        client = redis_client()
        client.ping()
        info = client.info("memory")
        cached = client.get(REDIS_KEY)
        cached_count = len(json.loads(cached)) if cached else 0
        used_bytes = int(info.get("used_memory", 0))
        peak_bytes = int(info.get("used_memory_peak", 0))
        max_bytes = int(info.get("maxmemory", 0))
        result["redis"] = {
            "connected": True,
            "used_bytes": used_bytes,
            "used_mb": round(used_bytes / (1024 * 1024), 3),
            "peak_bytes": peak_bytes,
            "peak_mb": round(peak_bytes / (1024 * 1024), 3),
            "maxmemory_bytes": max_bytes,
            "maxmemory_mb": round(max_bytes / (1024 * 1024), 3) if max_bytes else None,
            "cached": cached is not None,
            "cached_book_count": cached_count,
            "payload_bytes": len(cached.encode("utf-8")) if cached else 0,
            "payload_mb": round(len(cached.encode("utf-8")) / (1024 * 1024), 3) if cached else 0,
        }
    except Exception:
        result["errors"].append("Redis no responde. Revisa REDIS_URL y que Redis esté iniciado.")
    return result


@app.get("/")
def dashboard():
    return render_template("index.html")


@app.get("/api/status")
def status():
    snapshot = capacity_snapshot()
    return jsonify(snapshot)


@app.post("/api/cache/warm")
def warm_cache():
    try:
        books, hit = get_catalog_cached()
        payload_bytes = len(catalog_json(books).encode("utf-8"))
        return jsonify({"book_count": len(books), "payload_bytes": payload_bytes, "cache_hit": hit})
    except Exception:
        return jsonify({"error": "No se pudo cargar el catálogo. Verifica PostgreSQL y Redis."}), 503


@app.delete("/api/cache")
def clear_cache():
    try:
        deleted = redis_client().delete(REDIS_KEY)
        return jsonify({"deleted": bool(deleted)})
    except Exception:
        return jsonify({"error": "No se pudo borrar la clave de prueba en Redis."}), 503


@app.post("/api/benchmark")
def benchmark():
    body = request.get_json(silent=True) or {}
    try:
        iterations = int(body.get("iterations", 20))
    except (TypeError, ValueError):
        return jsonify({"error": "Las iteraciones deben ser un número entero."}), 400
    if not 3 <= iterations <= 100:
        return jsonify({"error": "Elige entre 3 y 100 iteraciones."}), 400

    try:
        client = redis_client()
        client.ping()
        first_books = query_catalog()
        source_payload = catalog_json(first_books)
        client.setex(REDIS_KEY, CACHE_TTL_SECONDS, source_payload)

        postgres_stats, postgres_result = measure(query_catalog, iterations)
        redis_hit_stats, redis_result = measure(lambda: get_catalog_cached(client), iterations)

        miss_timings = []
        miss_iterations = min(iterations, 20)
        for _ in range(miss_iterations):
            client.delete(REDIS_KEY)
            started = time.perf_counter_ns()
            get_catalog_cached(client)
            miss_timings.append((time.perf_counter_ns() - started) / 1_000_000)
        cache_miss_stats = summarize_timings(miss_timings)
        redis_payload = client.get(REDIS_KEY) or "[]"
        payload_bytes = len(redis_payload.encode("utf-8"))
        exact_match = postgres_result == redis_result[0]
        speedup = (
            round(postgres_stats["median_ms"] / redis_hit_stats["median_ms"], 2)
            if redis_hit_stats["median_ms"] > 0
            else None
        )

        return jsonify({
            "iterations": iterations,
            "cache_miss_iterations": miss_iterations,
            "book_count": len(postgres_result),
            "payload_bytes": payload_bytes,
            "payload_mb": round(payload_bytes / (1024 * 1024), 3),
            "results_match": exact_match,
            "speedup": speedup,
            "postgres_direct": postgres_stats,
            "redis_hit": redis_hit_stats,
            "redis_miss_fill": cache_miss_stats,
            "preview": postgres_result[:6],
            "capacity": capacity_snapshot(),
        })
    except Exception:
        return jsonify({"error": "La prueba requiere PostgreSQL y Redis disponibles, y el esquema esperado de libros."}), 503


if __name__ == "__main__":
    app.run(
        host=os.getenv("APP_HOST", "127.0.0.1"),
        port=int(os.getenv("APP_PORT", "5050")),
        debug=False,
    )