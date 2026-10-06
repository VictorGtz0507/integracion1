import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from shared import jwt_auth


class AuthorsSecurityTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_author_mutations_require_jwt(self):
        requests = (
            ("post", "/authors"),
            ("put", "/authors/1"),
            ("patch", "/authors/1"),
            ("delete", "/authors/1"),
            ("post", "/authors/1/books"),
            ("delete", "/authors/1/books/2"),
        )
        for method, path in requests:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, json={})
                self.assertEqual(response.status_code, 401)

    def test_customer_cannot_create_author(self):
        claims = {"user_id": 12, "role_id": 3, "role": "customer", "sub": "12", "jti": "test"}
        with patch.object(jwt_auth, "verify_request_token", return_value=(claims, None, None)):
            self.assertEqual(self.client.post("/authors", json={"name": "Author"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()