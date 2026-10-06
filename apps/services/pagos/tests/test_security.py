import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from shared import jwt_auth


class PaymentsSecurityTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_payment_reads_require_jwt(self):
        for path in ("/payments", "/payments/1"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)

    def test_payment_mutations_require_jwt(self):
        requests = (
            ("post", "/payments"),
            ("put", "/payments/1"),
            ("patch", "/payments/1"),
        )
        for method, path in requests:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, json={})
                self.assertEqual(response.status_code, 401)

    def test_customer_cannot_refund_payment(self):
        claims = {"user_id": 12, "role_id": 3, "role": "customer", "sub": "12", "jti": "test"}
        with patch.object(jwt_auth, "verify_request_token", return_value=(claims, None, None)):
            self.assertEqual(self.client.patch("/payments/1", json={"status": "refunded"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()