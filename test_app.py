import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


class CheckEndpointTests(unittest.TestCase):
    @patch("base.time.monotonic", return_value=0)
    def test_allowed_request(self, clock):
        response = client.post("/check", json={"user_id": "alice", "cost": 4})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["allowed"])
        self.assertEqual(body["tokens_remaining"], 6)

    @patch("base.time.monotonic", return_value=0)
    def test_rejected_request(self, clock):
        client.post("/check", json={"user_id": "bob", "cost": 10})

        response = client.post("/check", json={"user_id": "bob", "cost": 1})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["allowed"])


if __name__ == "__main__":
    unittest.main()
