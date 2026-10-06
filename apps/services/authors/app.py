import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import jsonify, request
from psycopg.rows import dict_row

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.jwt_auth import jwt_required
from shared.redis_support import invalidate_book_catalog_cache
from shared.service_support import create_service, ensure_library_schema, get_db_connection

app = create_service("library-authors-service")

AUTHOR_QUERY = """
    SELECT a.id, a.name, a.biography,
           COALESCE(json_agg(json_build_object('id', b.id, 'title', b.title, 'isbn', b.isbn)
               ORDER BY b.id) FILTER (WHERE b.id IS NOT NULL), '[]'::json) AS books
    FROM authors a
    LEFT JOIN book_authors ba ON ba.author_id = a.id
    LEFT JOIN books b ON b.id = ba.book_id
"""


@app.get("/authors")
def list_authors():
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(AUTHOR_QUERY + " GROUP BY a.id ORDER BY a.name")
            authors = cursor.fetchall()
    return jsonify(authors)


@app.get("/authors/<int:author_id>")
def get_author(author_id):
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(AUTHOR_QUERY + " WHERE a.id = %s GROUP BY a.id", (author_id,))
            author = cursor.fetchone()
    if author is None:
        return jsonify({"error": "Author not found"}), 404
    return jsonify(author)


@app.post("/authors")
@jwt_required(roles={"admin"})
def create_author():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "INSERT INTO authors (name, biography) VALUES (%s, %s) RETURNING id, name, biography",
                (name, str(data.get("biography", "")).strip()),
            )
            author = cursor.fetchone()
        connection.commit()
    invalidate_book_catalog_cache()
    return jsonify(author), 201


@app.route("/authors/<int:author_id>", methods=["PUT", "PATCH"])
@jwt_required(roles={"admin"})
def update_author(author_id):
    data = request.get_json(silent=True) or {}
    fields = {key: data[key] for key in ("name", "biography") if key in data}
    if not fields:
        return jsonify({"error": "name or biography is required"}), 400
    if "name" in fields and not str(fields["name"]).strip():
        return jsonify({"error": "name cannot be empty"}), 400
    assignments = [f"{key} = %s" for key in fields]
    values = [str(value).strip() for value in fields.values()]
    values.append(author_id)
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                f"UPDATE authors SET {', '.join(assignments)} WHERE id = %s RETURNING id, name, biography",
                tuple(values),
            )
            author = cursor.fetchone()
        connection.commit()
    invalidate_book_catalog_cache()
    if author is None:
        return jsonify({"error": "Author not found"}), 404
    return jsonify(author)


@app.delete("/authors/<int:author_id>")
@jwt_required(roles={"admin"})
def delete_author(author_id):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM book_authors WHERE author_id = %s", (author_id,))
            cursor.execute("DELETE FROM authors WHERE id = %s", (author_id,))
            deleted = cursor.rowcount
        connection.commit()
    invalidate_book_catalog_cache()
    if not deleted:
        return jsonify({"error": "Author not found"}), 404
    return jsonify({"deleted": True, "author_id": author_id})


@app.post("/authors/<int:author_id>/books")
@jwt_required(roles={"admin"})
def link_book(author_id):
    data = request.get_json(silent=True) or {}
    try:
        book_id = int(data.get("book_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "book_id must be an integer"}), 400
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM authors WHERE id = %s", (author_id,))
            if cursor.fetchone() is None:
                return jsonify({"error": "Author not found"}), 404
            cursor.execute("SELECT 1 FROM books WHERE id = %s", (book_id,))
            if cursor.fetchone() is None:
                return jsonify({"error": "Book not found"}), 404
            cursor.execute(
                "INSERT INTO book_authors (book_id, author_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (book_id, author_id),
            )
        connection.commit()
    invalidate_book_catalog_cache()
    return jsonify({"author_id": author_id, "book_id": book_id, "linked": True}), 201


@app.delete("/authors/<int:author_id>/books/<int:book_id>")
@jwt_required(roles={"admin"})
def unlink_book(author_id, book_id):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM book_authors WHERE author_id = %s AND book_id = %s",
                (author_id, book_id),
            )
            deleted = cursor.rowcount
        connection.commit()
    invalidate_book_catalog_cache()
    if not deleted:
        return jsonify({"error": "Author/book relationship not found"}), 404
    return jsonify({"author_id": author_id, "book_id": book_id, "linked": False})


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    ensure_library_schema()
    app.run(host=os.getenv("APP_HOST", "0.0.0.0"), port=int(os.getenv("PORT", "5003")), debug=False)