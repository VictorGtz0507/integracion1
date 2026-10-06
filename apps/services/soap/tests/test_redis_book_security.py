import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import os
os.environ.setdefault("JWT_SECRET_KEY", "unit-test-shared-signing-key-0123456789")
import jwt
import redis

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))
from shared import jwt_auth
import app as books_app
from shared.redis_support import RedisUnavailable


class RedisBookSecurityTests(unittest.TestCase):
    def test_filter_order_produces_stable_cache_key(self):
        first = books_app.cache_key_for_list({"author": ["Ursula"], "category": ["Sci-fi"]})
        second = books_app.cache_key_for_list({"category": ["Sci-fi"], "author": ["Ursula"]})
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("books:list:"))

    def test_public_cache_read_falls_back_when_redis_is_down(self):
        with books_app.app.app_context():
            with patch.object(books_app, "get_redis", side_effect=redis.ConnectionError("offline")):
                self.assertIsNone(books_app.read_cached_json("books:123"))

    def test_revoked_jwt_is_rejected(self):
        token = jwt.encode({"sub": "1", "user_id": 1, "role_id": 3, "role": "customer", "jti": "revoked-id", "iat": 1700000000, "exp": 4102444800}, books_app.app.config["JWT_SECRET_KEY"], algorithm="HS256")
        client = Mock()
        client.exists.return_value = 1
        with books_app.app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
            with patch.object(jwt_auth, "require_redis", return_value=client):
                valid, error, status = books_app.require_valid_jwt()
        self.assertFalse(valid)
        self.assertEqual(status, 401)
        self.assertEqual(error["error"], "Token revoked")

    def test_authorization_fails_closed_when_redis_is_down(self):
        token = jwt.encode({"sub": "1", "user_id": 1, "role_id": 3, "role": "customer", "jti": "active-id", "iat": 1700000000, "exp": 4102444800}, books_app.app.config["JWT_SECRET_KEY"], algorithm="HS256")
        with books_app.app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
            with patch.object(jwt_auth, "require_redis", side_effect=RedisUnavailable):
                valid, error, status = books_app.require_valid_jwt()
        self.assertFalse(valid)
        self.assertEqual(status, 503)
        self.assertIn("unavailable", error["error"])

    def test_protected_write_returns_503_when_redis_is_down(self):
        token = jwt.encode({"sub": "1", "user_id": 1, "role_id": 3, "role": "customer", "jti": "active-id", "iat": 1700000000, "exp": 4102444800}, books_app.app.config["JWT_SECRET_KEY"], algorithm="HS256")
        with patch.object(jwt_auth, "require_redis", side_effect=RedisUnavailable):
            response = books_app.app.test_client().post(
                "/api/books",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Never reached", "isbn": "123"},
            )
        self.assertEqual(response.status_code, 503)

    def test_customer_cannot_write_catalog(self):
        token = jwt.encode({"sub": "1", "user_id": 1, "role_id": 3, "role": "customer", "jti": "active-id", "iat": 1700000000, "exp": 4102444800}, books_app.app.config["JWT_SECRET_KEY"], algorithm="HS256")
        client = Mock()
        client.exists.return_value = 0
        with patch.object(jwt_auth, "require_redis", return_value=client):
            response = books_app.app.test_client().post(
                "/api/books",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Never reached", "isbn": "123"},
            )
        self.assertEqual(response.status_code, 403)

    def test_jwt_without_jti_is_rejected(self):
        token = jwt.encode({"sub": "1", "user_id": 1, "role_id": 3, "exp": 4102444800}, books_app.app.config["JWT_SECRET_KEY"], algorithm="HS256")
        with books_app.app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
            valid, error, status = books_app.require_valid_jwt()
        self.assertFalse(valid)
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()