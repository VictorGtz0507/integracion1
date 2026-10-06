import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import jwt
from flask import Flask, jsonify

os.environ.setdefault("JWT_SECRET_KEY", "unit-test-shared-signing-key-0123456789")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared import jwt_auth
from shared.redis_support import RedisUnavailable
from shared.service_support import create_service


def make_token(overrides=None, expires=None):
    claims = {
        "sub": "17",
        "user_id": 17,
        "role_id": 3,
        "role": "customer",
        "jti": "test-token-id",
        "iat": datetime.now(timezone.utc),
        "exp": expires or datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    claims.update(overrides or {})
    return jwt.encode(claims, os.environ["JWT_SECRET_KEY"], algorithm="HS256")


class JWTAuthTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

        @self.app.get("/protected")
        @jwt_auth.jwt_required()
        def protected():
            return jsonify({"user_id": self.app_context_claims_user()})

        @self.app.post("/admin")
        @jwt_auth.jwt_required(roles={"admin"})
        def admin():
            return jsonify({"ok": True})

        self.client = self.app.test_client()
        self.redis = Mock()
        self.redis.exists.return_value = 0

    def app_context_claims_user(self):
        from flask import request
        return request.jwt_claims["user_id"]

    def test_missing_token_is_401(self):
        response = self.client.get("/protected")
        self.assertEqual(response.status_code, 401)

    def test_expired_token_is_401(self):
        token = make_token(expires=datetime.now(timezone.utc) - timedelta(seconds=1))
        response = self.client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)

    def test_revoked_token_is_401(self):
        self.redis.exists.return_value = 1
        token = make_token()
        with patch.object(jwt_auth, "require_redis", return_value=self.redis):
            response = self.client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)

    def test_redis_outage_is_503(self):
        token = make_token()
        with patch.object(jwt_auth, "require_redis", side_effect=RedisUnavailable):
            response = self.client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 503)

    def test_non_admin_role_is_403(self):
        token = make_token()
        with patch.object(jwt_auth, "require_redis", return_value=self.redis):
            response = self.client.post("/admin", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 403)

    def test_required_role_claims_are_enforced(self):
        token = make_token(overrides={"role_id": None})
        response = self.client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)

    def test_missing_shared_jwt_secret_fails_closed(self):
        token = make_token()
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 503)

    def test_production_requires_explicit_cors_allowlist(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "CORS_ORIGINS"):
                create_service("misconfigured-production-service")

    def test_subject_must_match_user_id(self):
        token = make_token(overrides={"sub": "18"})
        response = self.client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)

    def test_unsigned_token_is_rejected(self):
        token = jwt.encode(
            {"sub": "17", "user_id": 17, "role_id": 3, "role": "customer", "jti": "unsigned", "iat": 1700000000, "exp": 4102444800},
            key=None,
            algorithm="none",
        )
        response = self.client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()