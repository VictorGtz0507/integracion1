import os
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import jwt
from flask import session

os.environ.setdefault("JWT_SECRET_KEY", "unit-test-shared-signing-key-0123456789")
os.environ.setdefault("REDIS_URL", "redis://:unit-test-password@127.0.0.1:6379/0")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as login_app
from app import ACCESS_TOKEN_TTL_SECONDS, REFRESH_TOKEN_TTL_SECONDS, app, create_token, refresh_key, save_refresh_token
from shared.redis_support import RedisUnavailable


class LoginTokenTests(unittest.TestCase):
    def test_access_token_has_jti_and_twenty_minute_expiration(self):
        token, token_id = create_token({"id": 7, "email": "reader@example.test", "first_name": "Reader", "role_id": 3, "role": "customer"})
        payload = jwt.decode(token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
        now = int(datetime.now(timezone.utc).timestamp())
        self.assertEqual(payload["jti"], token_id)
        self.assertEqual(payload["exp"] - payload["iat"], ACCESS_TOKEN_TTL_SECONDS)
        self.assertLessEqual(payload["exp"] - now, ACCESS_TOKEN_TTL_SECONDS)
        self.assertEqual(ACCESS_TOKEN_TTL_SECONDS, 1200)

    def test_refresh_token_is_hashed_in_redis_key_and_has_ttl(self):
        client = Mock()
        token = "opaque-refresh-secret"
        user = {"id": 7, "email": "reader@example.test", "first_name": "Reader", "role_id": 3, "role": "customer"}
        save_refresh_token(client, token, user, "access-jti")
        args = client.setex.call_args.args
        self.assertEqual(args[0], refresh_key(token))
        self.assertNotIn(token, args[0])
        self.assertEqual(args[1], REFRESH_TOKEN_TTL_SECONDS)
        self.assertEqual(json.loads(args[2]), {"user": user, "jti": "access-jti"})

    def test_redis_session_ttl_matches_refresh_ttl(self):
        self.assertEqual(app.config["PERMANENT_SESSION_LIFETIME"].total_seconds(), REFRESH_TOKEN_TTL_SECONDS)

    def test_refresh_rotates_token_and_revokes_previous_access_jti(self):
        old_refresh_token = "old-refresh-token"
        user = {"id": 7, "email": "reader@example.test", "first_name": "Reader", "role_id": 3, "role": "customer"}
        client = Mock()
        client.getdel.return_value = json.dumps({"user": user, "jti": "old-access-jti"})
        test_client = app.test_client()
        with patch.object(login_app, "require_redis", return_value=client):
            response = test_client.post(
                "/refresh?format=json",
                json={"refresh_token": old_refresh_token},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["expires_in"], ACCESS_TOKEN_TTL_SECONDS)
        client.setex.assert_any_call("jwt:revoked:old-access-jti", ACCESS_TOKEN_TTL_SECONDS, "1")
        self.assertNotEqual(response.json["refresh_token"], old_refresh_token)

    def test_logout_revokes_access_and_deletes_refresh_key(self):
        client = Mock()
        client.get.return_value = None
        with app.test_request_context("/logout?format=json"):
            session["refresh_key"] = "jwt:refresh:hashed-value"
            session["access_jti"] = "active-jti"
            session["access_exp"] = int(datetime.now(timezone.utc).timestamp()) + 300
            with patch.object(login_app, "require_redis", return_value=client):
                response, status = login_app.logout_user()
        self.assertEqual(status, 200)
        client.setex.assert_called_once()
        self.assertEqual(client.setex.call_args.args[0], "jwt:revoked:active-jti")
        client.delete.assert_called_once_with("jwt:refresh:hashed-value")

    def test_logout_does_not_claim_success_when_redis_is_down(self):
        with app.test_request_context("/logout?format=json"):
            with patch.object(login_app, "require_redis", side_effect=RedisUnavailable):
                response, status = login_app.logout_user()
        self.assertEqual(status, 503)

    def test_login_endpoint_returns_503_when_redis_is_down(self):
        with patch.object(login_app, "require_redis", side_effect=RedisUnavailable):
            response = app.test_client().post(
                "/login?format=json",
                json={"email": "reader@example.test", "password": "secret"},
            )
        self.assertEqual(response.status_code, 503)

    def test_registration_does_not_return_internal_exception_details(self):
        with patch.object(login_app, "get_connection", side_effect=RuntimeError("sensitive database diagnostic")):
            response = app.test_client().post(
                "/register?format=json",
                json={
                    "first_name": "Reader",
                    "paternal_last_name": "Example",
                    "email": "reader@example.test",
                    "password": "never-return-this-password",
                },
            )
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("sensitive database diagnostic", response.get_data(as_text=True))
        self.assertNotIn("never-return-this-password", response.get_data(as_text=True))



if __name__ == "__main__":
    unittest.main()