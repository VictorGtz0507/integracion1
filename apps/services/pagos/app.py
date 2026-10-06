import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import jsonify, request
from psycopg.rows import dict_row

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.jwt_auth import jwt_required
from shared.service_support import create_service, ensure_library_schema, get_db_connection

app = create_service("library-payments-service")


@app.get("/payments")
@jwt_required()
def list_payments():
    claims = request.jwt_claims
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            if claims.get("role") == "admin":
                cursor.execute("SELECT * FROM payments ORDER BY created_at DESC")
            else:
                cursor.execute("SELECT * FROM payments WHERE user_id = %s ORDER BY created_at DESC", (claims["user_id"],))
            payments = cursor.fetchall()
    return jsonify(payments)


@app.get("/payments/<int:payment_id>")
@jwt_required()
def get_payment(payment_id):
    claims = request.jwt_claims
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SELECT * FROM payments WHERE id = %s", (payment_id,))
            payment = cursor.fetchone()
    if payment is None:
        return jsonify({"error": "Payment not found"}), 404
    if claims.get("role") != "admin" and int(payment["user_id"]) != int(claims["user_id"]):
        return jsonify({"error": "Insufficient role"}), 403
    return jsonify(payment)


@app.post("/payments")
@jwt_required()
def record_payment():
    data = request.get_json(silent=True) or {}
    try:
        order_id = int(data.get("order_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "order_id must be an integer"}), 400
    method = str(data.get("method", "manual")).strip().lower()
    if not method or len(method) > 40:
        return jsonify({"error": "method must contain 1 to 40 characters"}), 400

    claims = request.jwt_claims
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SELECT id, user_id, status, total_cents FROM orders WHERE id = %s FOR UPDATE", (order_id,))
            order = cursor.fetchone()
            if order is None:
                return jsonify({"error": "Order not found"}), 404
            if claims.get("role") != "admin" and int(order["user_id"]) != int(claims["user_id"]):
                return jsonify({"error": "Insufficient role"}), 403
            if order["status"] != "pending":
                return jsonify({"error": "Only pending orders can be paid"}), 409
            cursor.execute(
                """
                INSERT INTO payments (order_id, user_id, amount_cents, method, status, provider_reference)
                VALUES (%s, %s, %s, %s, 'succeeded', %s)
                RETURNING id, order_id, user_id, amount_cents, currency, method, status,
                          provider_reference, created_at
                """,
                (order_id, order["user_id"], order["total_cents"], method, uuid.uuid4()),
            )
            payment = cursor.fetchone()
            cursor.execute(
                "UPDATE orders SET status = 'paid', updated_at = NOW() WHERE id = %s",
                (order_id,),
            )
        connection.commit()
    return jsonify(payment), 201


@app.route("/payments/<int:payment_id>", methods=["PUT", "PATCH"])
@jwt_required(roles={"admin"})
def update_payment(payment_id):
    data = request.get_json(silent=True) or {}
    if data.get("status") != "refunded":
        return jsonify({"error": "Only a refund status update is supported"}), 400
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SELECT id, order_id, status FROM payments WHERE id = %s FOR UPDATE", (payment_id,))
            payment = cursor.fetchone()
            if payment is None:
                return jsonify({"error": "Payment not found"}), 404
            if payment["status"] != "succeeded":
                return jsonify({"error": "Only successful payments can be refunded"}), 409
            cursor.execute("SELECT status FROM orders WHERE id = %s FOR UPDATE", (payment["order_id"],))
            order = cursor.fetchone()
            if order is None or order["status"] != "paid":
                return jsonify({"error": "Order is not in a refundable state"}), 409
            cursor.execute("UPDATE orders SET status = 'refunded', updated_at = NOW() WHERE id = %s", (payment["order_id"],))
            if cursor.rowcount != 1:
                return jsonify({"error": "Order is not in a refundable state"}), 409
            cursor.execute("UPDATE payments SET status = 'refunded' WHERE id = %s", (payment_id,))
            cursor.execute("SELECT * FROM payments WHERE id = %s", (payment_id,))
            updated = cursor.fetchone()
        connection.commit()
    return jsonify(updated)


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    ensure_library_schema()
    app.run(host=os.getenv("APP_HOST", "0.0.0.0"), port=int(os.getenv("PORT", "5005")), debug=False)