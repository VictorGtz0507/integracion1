import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from shared import jwt_auth


class UsersSecurityTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_user_administration_reads_require_jwt(self):
        for path in ("/users", "/users/1", "/roles"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)

    def test_user_mutations_require_jwt(self):
        requests = (
            ("post", "/users"),
            ("put", "/users/1"),
            ("patch", "/users/1"),
            ("delete", "/users/1"),
        )
        for method, path in requests:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, json={})
                self.assertEqual(response.status_code, 401)

    def test_profile_requires_jwt(self):
        self.assertEqual(self.client.get("/users/me").status_code, 401)

    def test_customer_cannot_read_or_mutate_user_administration(self):
        claims = {"user_id": 12, "role_id": 3, "role": "customer", "sub": "12", "jti": "test"}
        with patch.object(jwt_auth, "verify_request_token", return_value=(claims, None, None)):
            self.assertEqual(self.client.get("/users").status_code, 403)
            self.assertEqual(self.client.post("/users", json={}).status_code, 403)


if __name__ == "__main__":
    unittest.main()