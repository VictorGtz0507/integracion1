import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import jsonify, request
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.jwt_auth import jwt_required
from shared.service_support import create_service, ensure_library_schema, get_db_connection

app = create_service("library-users-service")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.get("/users/me")
@jwt_required()
def current_user():
    user_id = request.jwt_claims["user_id"]
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT u.id, u.first_name, u.paternal_last_name, u.maternal_last_name,
                       u.email, u.role_id, r.role_name AS role, u.created_at
                FROM auth_users u JOIN roles r ON r.role_id = u.role_id WHERE u.id = %s
                """,
                (user_id,),
            )
            user = cursor.fetchone()
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)


@app.get("/roles")
@jwt_required(roles={"admin"})
def list_roles():
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SELECT role_id, role_name FROM roles ORDER BY role_id")
            roles = cursor.fetchall()
    return jsonify(roles)


@app.get("/users")
@jwt_required(roles={"admin"})
def list_users():
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT u.id, u.first_name, u.paternal_last_name, u.maternal_last_name,
                       u.email, u.role_id, r.role_name AS role, u.created_at
                FROM auth_users u JOIN roles r ON r.role_id = u.role_id
                ORDER BY u.id
                """
            )
            users = cursor.fetchall()
    return jsonify(users)


@app.get("/users/<int:user_id>")
@jwt_required()
def get_user(user_id):
    claims = request.jwt_claims
    if claims.get("role") != "admin" and int(claims["user_id"]) != user_id:
        return jsonify({"error": "Insufficient role"}), 403
    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT u.id, u.first_name, u.paternal_last_name, u.maternal_last_name,
                       u.email, u.role_id, r.role_name AS role, u.created_at
                FROM auth_users u JOIN roles r ON r.role_id = u.role_id WHERE u.id = %s
                """,
                (user_id,),
            )
            user = cursor.fetchone()
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)


@app.post("/users")
@jwt_required(roles={"admin"})
def create_user():
    data = request.get_json(silent=True) or {}
    required = ("first_name", "paternal_last_name", "email", "password")
    if any(not str(data.get(field, "")).strip() for field in required):
        return jsonify({"error": "first_name, paternal_last_name, email and password are required"}), 400
    email = str(data["email"]).strip().lower()
    if not EMAIL_PATTERN.match(email):
        return jsonify({"error": "Invalid email format"}), 400
    password = str(data["password"])
    if len(password) < 12:
        return jsonify({"error": "Password must contain at least 12 characters"}), 400
    role_name = str(data.get("role", "customer")).strip().lower()
    try:
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SELECT role_id FROM roles WHERE role_name = %s", (role_name,))
                role = cursor.fetchone()
                if role is None:
                    return jsonify({"error": "Unknown role"}), 400
                cursor.execute(
                    """
                    INSERT INTO auth_users
                        (first_name, paternal_last_name, maternal_last_name, email, password_hash, role_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, first_name, paternal_last_name, maternal_last_name, email, role_id, created_at
                    """,
                    (
                        str(data["first_name"]).strip(),
                        str(data["paternal_last_name"]).strip(),
                        str(data.get("maternal_last_name", "")).strip(),
                        email,
                        generate_password_hash(password),
                        role["role_id"],
                    ),
                )
                user = cursor.fetchone()
            connection.commit()
    except UniqueViolation:
        return jsonify({"error": "Email already registered"}), 409
    return jsonify(user), 201


@app.route("/users/<int:user_id>", methods=["PUT", "PATCH"])
@jwt_required(roles={"admin"})
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    allowed = {"first_name", "paternal_last_name", "maternal_last_name", "email", "password", "role"}
    changes = {key: value for key, value in data.items() if key in allowed}
    if not changes:
        return jsonify({"error": "No supported fields provided"}), 400

    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SELECT role_id FROM auth_users WHERE id = %s", (user_id,))
            if cursor.fetchone() is None:
                return jsonify({"error": "User not found"}), 404

            updates = []
            values = []
            for key in ("first_name", "paternal_last_name", "maternal_last_name", "email"):
                if key in changes:
                    value = str(changes[key]).strip()
                    if key == "email":
                        value = value.lower()
                        if not EMAIL_PATTERN.match(value):
                            return jsonify({"error": "Invalid email format"}), 400
                    updates.append(f"{key} = %s")
                    values.append(value)
            if "password" in changes:
                password = str(changes["password"])
                if len(password) < 12:
                    return jsonify({"error": "Password must contain at least 12 characters"}), 400
                updates.append("password_hash = %s")
                values.append(generate_password_hash(password))
            if "role" in changes:
                cursor.execute("SELECT role_id FROM roles WHERE role_name = %s", (str(changes["role"]).lower(),))
                role = cursor.fetchone()
                if role is None:
                    return jsonify({"error": "Unknown role"}), 400
                updates.append("role_id = %s")
                values.append(role["role_id"])

            values.append(user_id)
            cursor.execute(
                f"UPDATE auth_users SET {', '.join(updates)} WHERE id = %s RETURNING id, first_name, paternal_last_name, maternal_last_name, email, role_id, created_at",
                tuple(values),
            )
            user = cursor.fetchone()
        connection.commit()
    return jsonify(user)


@app.delete("/users/<int:user_id>")
@jwt_required(roles={"admin"})
def delete_user(user_id):
    if int(request.jwt_claims["user_id"]) == user_id:
        return jsonify({"error": "Administrators cannot delete their own account"}), 409
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM auth_users WHERE id = %s", (user_id,))
                deleted = cursor.rowcount
            connection.commit()
    except ForeignKeyViolation:
        return jsonify({"error": "User has orders or records and cannot be deleted"}), 409
    if not deleted:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"deleted": True, "user_id": user_id})


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    ensure_library_schema()
    app.run(host=os.getenv("APP_HOST", "0.0.0.0"), port=int(os.getenv("PORT", "5002")), debug=False)