import os
import hashlib
import json
import sys
import time
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path

import psycopg2
import redis
from dotenv import load_dotenv
from flask import Flask, current_app, jsonify, request
from flask_cors import CORS
from psycopg2.extras import RealDictCursor

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.jwt_auth import verify_request_token
from shared.redis_support import RedisUnavailable, get_redis, invalidate_book_catalog_cache, metrics_snapshot, record_metric, require_redis

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
BOOKS_CACHE_TTL_SECONDS = int(os.getenv("BOOKS_CACHE_TTL_SECONDS", "60"))
if os.getenv("APP_ENV", "development").lower() == "production" and not os.getenv("CORS_ORIGINS"):
    raise RuntimeError("CORS_ORIGINS must be configured in production")
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                origin.strip()
                for origin in (
                    os.getenv("CORS_ORIGINS")
                    or (
                        ""
                        if os.getenv("APP_ENV", "development").lower() == "production"
                        else "http://localhost:3000,http://127.0.0.1:3000"
                    )
                ).split(",")
                if origin.strip()
            ]
        }
    },
    supports_credentials=True,
)


def cache_key_for_list(filters=None):
    normalized = json.dumps(filters or {}, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"books:list:{digest}"


def read_cached_json(key):
    started = time.perf_counter()
    try:
        value = get_redis().get(key)
        record_metric("books.cache_hit" if value is not None else "books.cache_miss", started)
        return current_app.json.loads(value) if value is not None else None
    except (redis.RedisError, RedisUnavailable):
        record_metric("books.cache_error", started, failed=True)
        return None


def write_cached_json(key, value):
    started = time.perf_counter()
    try:
        get_redis().setex(key, BOOKS_CACHE_TTL_SECONDS, current_app.json.dumps(value))
        record_metric("books.cache_write", started)
    except (redis.RedisError, RedisUnavailable):
        record_metric("books.cache_error", started, failed=True)


def invalidate_book_caches():
    invalidate_book_catalog_cache()


def get_db_config():
    return {
        "dbname": os.getenv("DB_NAME", "library_db"),
        "user": os.getenv("DB_USER", "library_user"),
        "password": os.getenv("DB_PASSWORD", "666"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
    }


def get_token_from_request():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header.split(" ", 1)[1].strip()


def require_valid_jwt():
    payload, error, status = verify_request_token()
    if error:
        return False, error, status
    request.jwt_payload = payload
    return True, None, None


def get_connection():
    return psycopg2.connect(**get_db_config())


def decimal_to_cents(value):
    if value is None:
        return 0
    try:
        return int((Decimal(str(value)) * 100).quantize(Decimal("1")))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid price value")


def cents_to_decimal(value):
    if value is None:
        return 0.0
    return Decimal(value) / Decimal(100)


def _normalize_names(values):
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    result = []
    for item in values:
        if item is None:
            continue
        name = str(item).strip()
        if name:
            result.append(name)
    return result


def _upsert_author(conn, author_name):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM authors WHERE name = %s LIMIT 1", (author_name,))
        existing = cur.fetchone()
        if existing:
            return existing[0]

        cur.execute(
            "INSERT INTO authors (name, biography) VALUES (%s, %s) RETURNING id",
            (author_name, ""),
        )
        return cur.fetchone()[0]


def _upsert_category(conn, category_name):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM categories WHERE name = %s LIMIT 1", (category_name,))
        existing = cur.fetchone()
        if existing:
            return existing[0]

        cur.execute(
            "INSERT INTO categories (name, description) VALUES (%s, %s) RETURNING id",
            (category_name, ""),
        )
        return cur.fetchone()[0]


def _load_book_relations(book_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT a.name AS author_name FROM authors a INNER JOIN book_authors ba ON ba.author_id = a.id WHERE ba.book_id = %s ORDER BY a.name",
                (book_id,),
            )
            authors = [row["author_name"] for row in cur.fetchall()]

            cur.execute(
                "SELECT c.name AS category_name FROM categories c INNER JOIN book_categories bc ON bc.category_id = c.id WHERE bc.book_id = %s ORDER BY c.name",
                (book_id,),
            )
            categories = [row["category_name"] for row in cur.fetchall()]

            cur.execute(
                "SELECT term, definition FROM concepts WHERE book_id = %s ORDER BY term",
                (book_id,),
            )
            concepts = [
                {"term": row["term"], "definition": row["definition"]}
                for row in cur.fetchall()
            ]

            cur.execute(
                "SELECT id, filename, original_name, mime_type FROM images WHERE book_id = %s ORDER BY id",
                (book_id,),
            )
            images = [
                {
                    "id": row["id"],
                    "filename": row["filename"],
                    "original_name": row["original_name"],
                    "mime_type": row["mime_type"],
                }
                for row in cur.fetchall()
            ]

    return {"authors": authors, "categories": categories, "concepts": concepts, "images": images}


def serialize_book(book_row):
    book = dict(book_row)
    relations = _load_book_relations(book["id"])
    book["authors"] = relations["authors"]
    book["categories"] = relations["categories"]
    book["concepts"] = relations["concepts"]
    book["images"] = relations["images"]
    book["price"] = float(cents_to_decimal(book.get("price_cents", 0)))
    book.pop("price_cents", None)
    return book


def load_book_by_id(book_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM books WHERE id = %s",
                (book_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return serialize_book(row)


def load_book_by_isbn(isbn):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM books WHERE isbn = %s",
                (isbn,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return serialize_book(row)


def jwt_required(roles=None):
    required_roles = set(roles or [])

    def decorate(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ok, payload, status = require_valid_jwt()
            if not ok:
                return jsonify(payload), status
            if required_roles and request.jwt_payload.get("role") not in required_roles:
                return jsonify({"error": "Insufficient role"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorate


@app.route("/health", methods=["GET"])
def health():
    try:
        require_redis()
        redis_status = "connected"
    except RedisUnavailable:
        redis_status = "unavailable"
    return jsonify({
        "status": "ok" if redis_status == "connected" else "degraded",
        "service": "library-book-service",
        "redis": redis_status,
    }), (200 if redis_status == "connected" else 503)


@app.route("/metrics", methods=["GET"])
def metrics():
    return jsonify(metrics_snapshot())


@app.route("/api/books", methods=["GET"])
@app.route("/books", methods=["GET"])
def get_books():
    key = cache_key_for_list()
    cached = read_cached_json(key)
    if cached is not None:
        return jsonify(cached), 200
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM books ORDER BY id")
                rows = cur.fetchall()

        books = [serialize_book(row) for row in rows]
        write_cached_json(key, books)
        return jsonify(books), 200
    except Exception as exc:  # pragma: no cover - defensive handling
        return jsonify({"error": str(exc)}), 500


@app.route("/api/books/search", methods=["GET"])
@app.route("/books/search", methods=["GET"])
def search_books():
    filters_snapshot = request.args.to_dict(flat=False)
    cache_key = cache_key_for_list(filters_snapshot)
    cached = read_cached_json(cache_key)
    if cached is not None:
        return jsonify(cached), 200

    filters = []
    values = []

    title = request.args.get("title")
    isbn = request.args.get("isbn")
    author = request.args.get("author")
    category = request.args.get("category")
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    min_stock = request.args.get("min_stock")
    max_stock = request.args.get("max_stock")
    published_year = request.args.get("published_year")

    if title:
        filters.append("b.title ILIKE %s")
        values.append(f"%{title}%")
    if isbn:
        filters.append("b.isbn ILIKE %s")
        values.append(f"%{isbn}%")
    if published_year:
        filters.append("b.published_year = %s")
        values.append(published_year)
    if min_price:
        filters.append("b.price_cents >= %s")
        values.append(decimal_to_cents(min_price))
    if max_price:
        filters.append("b.price_cents <= %s")
        values.append(decimal_to_cents(max_price))
    if min_stock:
        filters.append("b.stock >= %s")
        values.append(int(min_stock))
    if max_stock:
        filters.append("b.stock <= %s")
        values.append(int(max_stock))

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if author or category:
                    base_sql = """
                        SELECT DISTINCT b.*
                        FROM books b
                        LEFT JOIN book_authors ba ON ba.book_id = b.id
                        LEFT JOIN authors a ON a.id = ba.author_id
                        LEFT JOIN book_categories bc ON bc.book_id = b.id
                        LEFT JOIN categories c ON c.id = bc.category_id
                        WHERE 1 = 1
                    """
                    if author:
                        filters.append("a.name ILIKE %s")
                        values.append(f"%{author}%")
                    if category:
                        filters.append("c.name ILIKE %s")
                        values.append(f"%{category}%")

                    sql = base_sql + (" AND " + " AND ".join(filters) if filters else "") + " ORDER BY b.id"
                    cur.execute(sql, tuple(values))
                    rows = cur.fetchall()
                else:
                    sql = "SELECT b.* FROM books b WHERE 1 = 1"
                    if filters:
                        sql += " AND " + " AND ".join(filters)
                    sql += " ORDER BY b.id"
                    cur.execute(sql, tuple(values))
                    rows = cur.fetchall()

        books = [serialize_book(row) for row in rows]
        write_cached_json(cache_key, books)
        return jsonify(books), 200
    except Exception as exc:  # pragma: no cover - defensive handling
        return jsonify({"error": str(exc)}), 500


@app.route("/api/books/<isbn>", methods=["GET"])
@app.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id=None, isbn=None):
    if isbn is not None:
        cache_key = f"books:{isbn}"
        cached = read_cached_json(cache_key)
        if cached is not None:
            return jsonify(cached), 200
        book = load_book_by_isbn(isbn)
        if book is not None:
            write_cached_json(cache_key, book)
    else:
        book = load_book_by_id(book_id)
    if book is None:
        return jsonify({"error": "Book not found"}), 404
    return jsonify(book), 200


@app.route("/api/books", methods=["POST"])
@app.route("/books", methods=["POST"])
@jwt_required(roles={"admin"})
def create_book():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or payload.get("titulo") or "").strip()
    isbn = (payload.get("isbn") or "").strip()
    description = payload.get("description") or payload.get("descripcion") or ""
    price = payload.get("price")
    stock = payload.get("stock", 0)
    published_year = payload.get("published_year") or payload.get("publicationYear")

    if not title or not isbn:
        return jsonify({"error": "title and isbn are required"}), 400

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO books (title, isbn, description, price_cents, stock, published_year) VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
                    (
                        title,
                        isbn,
                        description,
                        decimal_to_cents(price) if price is not None else 0,
                        int(stock),
                        int(published_year) if published_year not in (None, "") else None,
                    ),
                )
                new_book = cur.fetchone()
                book_id = new_book["id"]

                for author_name in _normalize_names(payload.get("authors")):
                    author_id = _upsert_author(conn, author_name)
                    cur.execute(
                        "INSERT INTO book_authors (book_id, author_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (book_id, author_id),
                    )

                for category_name in _normalize_names(payload.get("categories")):
                    category_id = _upsert_category(conn, category_name)
                    cur.execute(
                        "INSERT INTO book_categories (book_id, category_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (book_id, category_id),
                    )

                for concept in payload.get("concepts", []) or []:
                    if isinstance(concept, dict):
                        term = (concept.get("term") or concept.get("name") or "").strip()
                        definition = (concept.get("definition") or "").strip()
                    elif isinstance(concept, list) and len(concept) >= 2:
                        term, definition = str(concept[0]).strip(), str(concept[1]).strip()
                    else:
                        continue
                    if not term:
                        continue
                    cur.execute(
                        "INSERT INTO concepts (book_id, term, definition) VALUES (%s, %s, %s) ON CONFLICT (book_id, term) DO UPDATE SET definition = EXCLUDED.definition",
                        (book_id, term, definition),
                    )

                for image in payload.get("images", []) or []:
                    if isinstance(image, dict):
                        filename = (image.get("filename") or image.get("url") or "").strip()
                        original_name = image.get("original_name") or filename or "image"
                        mime_type = image.get("mime_type") or "image/jpeg"
                    else:
                        filename = str(image).strip()
                        original_name = filename or "image"
                        mime_type = "image/jpeg"
                    if not filename:
                        continue
                    cur.execute(
                        "INSERT INTO images (book_id, filename, original_name, mime_type) VALUES (%s, %s, %s, %s)",
                        (book_id, filename, original_name, mime_type),
                    )

            conn.commit()
            invalidate_book_caches()
            created = load_book_by_id(book_id)
            return jsonify(created), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover - defensive handling
        return jsonify({"error": str(exc)}), 500


@app.route("/api/books/<int:book_id>", methods=["PUT", "PATCH"])
@app.route("/books/<int:book_id>", methods=["PUT", "PATCH"])
@jwt_required(roles={"admin"})
def update_book(book_id):
    payload = request.get_json(silent=True) or {}
    if not payload:
        return jsonify({"error": "Request body cannot be empty"}), 400

    existing = load_book_by_id(book_id)
    if existing is None:
        return jsonify({"error": "Book not found"}), 404

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                title = payload.get("title") or payload.get("titulo") or existing["title"]
                isbn = payload.get("isbn") or existing["isbn"]
                description = payload.get("description") or payload.get("descripcion") or existing.get("description", "")
                stock = payload.get("stock", existing.get("stock", 0))
                published_year = payload.get("published_year")
                if published_year is None and "publicationYear" in payload:
                    published_year = payload.get("publicationYear")
                if published_year is None:
                    published_year = existing.get("published_year")
                price = payload.get("price")
                if price is None:
                    price_cents = existing.get("price", 0) * 100
                else:
                    price_cents = decimal_to_cents(price)

                cur.execute(
                    "UPDATE books SET title = %s, isbn = %s, description = %s, price_cents = %s, stock = %s, published_year = %s WHERE id = %s",
                    (
                        title,
                        isbn,
                        description,
                        int(price_cents),
                        int(stock),
                        int(published_year) if published_year not in (None, "") else None,
                        book_id,
                    ),
                )

                if "authors" in payload:
                    cur.execute("DELETE FROM book_authors WHERE book_id = %s", (book_id,))
                    for author_name in _normalize_names(payload.get("authors")):
                        author_id = _upsert_author(conn, author_name)
                        cur.execute(
                            "INSERT INTO book_authors (book_id, author_id) VALUES (%s, %s)",
                            (book_id, author_id),
                        )

                if "categories" in payload:
                    cur.execute("DELETE FROM book_categories WHERE book_id = %s", (book_id,))
                    for category_name in _normalize_names(payload.get("categories")):
                        category_id = _upsert_category(conn, category_name)
                        cur.execute(
                            "INSERT INTO book_categories (book_id, category_id) VALUES (%s, %s)",
                            (book_id, category_id),
                        )

                if "concepts" in payload:
                    cur.execute("DELETE FROM concepts WHERE book_id = %s", (book_id,))
                    for concept in payload.get("concepts", []) or []:
                        if isinstance(concept, dict):
                            term = (concept.get("term") or concept.get("name") or "").strip()
                            definition = (concept.get("definition") or "").strip()
                        elif isinstance(concept, list) and len(concept) >= 2:
                            term, definition = str(concept[0]).strip(), str(concept[1]).strip()
                        else:
                            continue
                        if term:
                            cur.execute(
                                "INSERT INTO concepts (book_id, term, definition) VALUES (%s, %s, %s)",
                                (book_id, term, definition),
                            )

                if "images" in payload:
                    cur.execute("DELETE FROM images WHERE book_id = %s", (book_id,))
                    for image in payload.get("images", []) or []:
                        if isinstance(image, dict):
                            filename = (image.get("filename") or image.get("url") or "").strip()
                            original_name = image.get("original_name") or filename or "image"
                            mime_type = image.get("mime_type") or "image/jpeg"
                        else:
                            filename = str(image).strip()
                            original_name = filename or "image"
                            mime_type = "image/jpeg"
                        if filename:
                            cur.execute(
                                "INSERT INTO images (book_id, filename, original_name, mime_type) VALUES (%s, %s, %s, %s)",
                                (book_id, filename, original_name, mime_type),
                            )

            conn.commit()
            invalidate_book_caches()
            updated = load_book_by_id(book_id)
            return jsonify(updated), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover - defensive handling
        return jsonify({"error": str(exc)}), 500


@app.route("/api/books/<int:book_id>", methods=["DELETE"])
@app.route("/books/<int:book_id>", methods=["DELETE"])
@jwt_required(roles={"admin"})
def delete_book(book_id):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM books WHERE id = %s", (book_id,))
            conn.commit()
        invalidate_book_caches()
        return jsonify({"deleted": True, "book_id": book_id}), 200
    except Exception as exc:  # pragma: no cover - defensive handling
        return jsonify({"error": str(exc)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed"}), 405


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=False)
