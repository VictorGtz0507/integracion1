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

app = create_service("library-orders-service")
ORDER_STATUSES = {"pending", "paid", "processing", "shipped", "completed", "cancelled", "refunded"}
ALLOWED_TRANSITIONS = {
    "pending": {"cancelled"},
    "paid": {"processing"},
    "processing": {"shipped"},
    "shipped": {"completed"},
    "completed": set(),
    "cancelled": set(),
    "refunded": set(),
}


@app.get("/orders")
@jwt_required()
def list_orders():
    claims = request.jwt_claims
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            if claims.get("role") == "admin":
                cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")
            else:
                cursor.execute("SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC", (claims["user_id"],))
            orders = cursor.fetchall()
    return jsonify(orders)


@app.get("/orders/<int:order_id>")
@jwt_required()
def get_order(order_id):
    claims = request.jwt_claims
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if order is None:
                return jsonify({"error": "Order not found"}), 404
            if claims.get("role") != "admin" and int(order["user_id"]) != int(claims["user_id"]):
                return jsonify({"error": "Insufficient role"}), 403
            cursor.execute(
                "SELECT id, book_id, quantity, unit_price_cents, line_total_cents FROM order_items WHERE order_id = %s ORDER BY id",
                (order_id,),
            )
            order["items"] = cursor.fetchall()
    return jsonify(order)


@app.post("/orders")
@jwt_required()
def create_order():
    data = request.get_json(silent=True) or {}
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return jsonify({"error": "items must be a non-empty list"}), 400
    quantities = {}
    for item in items:
        if not isinstance(item, dict):
            return jsonify({"error": "Each item must contain book_id and quantity"}), 400
        try:
            book_id = int(item["book_id"])
            quantity = int(item["quantity"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "book_id and quantity must be integers"}), 400
        if book_id < 1 or quantity < 1:
            return jsonify({"error": "book_id and quantity must be positive"}), 400
        quantities[book_id] = quantities.get(book_id, 0) + quantity

    try:
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "INSERT INTO orders (user_id, status, total_cents) VALUES (%s, 'pending', 0) RETURNING *",
                    (request.jwt_claims["user_id"],),
                )
                order = cursor.fetchone()
                total_cents = 0
                for book_id, quantity in quantities.items():
                    cursor.execute(
                        "SELECT id, price_cents, stock FROM books WHERE id = %s FOR UPDATE",
                        (book_id,),
                    )
                    book = cursor.fetchone()
                    if book is None:
                        raise ValueError(f"Book {book_id} not found")
                    if int(book["stock"]) < quantity:
                        raise ValueError(f"Insufficient stock for book {book_id}")
                    unit_price = int(book["price_cents"])
                    line_total = unit_price * quantity
                    cursor.execute("UPDATE books SET stock = stock - %s WHERE id = %s", (quantity, book_id))
                    cursor.execute(
                        "INSERT INTO order_items (order_id, book_id, quantity, unit_price_cents, line_total_cents) VALUES (%s, %s, %s, %s, %s)",
                        (order["id"], book_id, quantity, unit_price, line_total),
                    )
                    total_cents += line_total
                cursor.execute(
                    "UPDATE orders SET total_cents = %s, updated_at = NOW() WHERE id = %s RETURNING *",
                    (total_cents, order["id"]),
                )
                order = cursor.fetchone()
                cursor.execute(
                    "SELECT id, book_id, quantity, unit_price_cents, line_total_cents FROM order_items WHERE order_id = %s ORDER BY id",
                    (order["id"],),
                )
                order["items"] = cursor.fetchall()
            connection.commit()
            invalidate_book_catalog_cache()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(order), 201


def change_order_status(order_id, new_status):
    if new_status not in ORDER_STATUSES:
        return jsonify({"error": "Invalid order status"}), 400
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SELECT id, status FROM orders WHERE id = %s FOR UPDATE", (order_id,))
            order = cursor.fetchone()
            if order is None:
                return jsonify({"error": "Order not found"}), 404
            if new_status not in ALLOWED_TRANSITIONS[order["status"]]:
                return jsonify({"error": f"Transition from {order['status']} to {new_status} is not allowed"}), 409
            if new_status == "cancelled":
                cursor.execute("SELECT book_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
                for item in cursor.fetchall():
                    cursor.execute("UPDATE books SET stock = stock + %s WHERE id = %s", (item["quantity"], item["book_id"]))
            cursor.execute(
                "UPDATE orders SET status = %s, updated_at = NOW() WHERE id = %s RETURNING *",
                (new_status, order_id),
            )
            updated = cursor.fetchone()
        connection.commit()
    if new_status == "cancelled":
        invalidate_book_catalog_cache()
    return jsonify(updated)


@app.route("/orders/<int:order_id>", methods=["PUT", "PATCH"])
@jwt_required(roles={"admin"})
def update_order(order_id):
    data = request.get_json(silent=True) or {}
    return change_order_status(order_id, str(data.get("status", "")))


@app.delete("/orders/<int:order_id>")
@jwt_required(roles={"admin"})
def delete_order(order_id):
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SELECT id, status FROM orders WHERE id = %s FOR UPDATE", (order_id,))
            order = cursor.fetchone()
            if order is None:
                return jsonify({"error": "Order not found"}), 404
            if order["status"] != "pending":
                return jsonify({"error": "Only pending orders can be deleted"}), 409
            cursor.execute("SELECT book_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
            for item in cursor.fetchall():
                cursor.execute("UPDATE books SET stock = stock + %s WHERE id = %s", (item["quantity"], item["book_id"]))
            cursor.execute("DELETE FROM orders WHERE id = %s", (order_id,))
        connection.commit()
    invalidate_book_catalog_cache()
    return jsonify({"deleted": True, "order_id": order_id})


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    ensure_library_schema()
    app.run(host=os.getenv("APP_HOST", "0.0.0.0"), port=int(os.getenv("PORT", "5004")), debug=False)