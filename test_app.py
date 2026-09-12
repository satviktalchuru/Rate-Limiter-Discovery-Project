import unittest
import uuid

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


class CheckEndpointTests(unittest.TestCase):
    def test_allowed_request(self):
        user_id = f"alice-{uuid.uuid4().hex}"
        response = client.post("/check", json={"user_id": user_id, "cost": 4})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["allowed"])
        self.assertEqual(body["tokens_remaining"], 6)

    def test_rejected_request_returns_429(self):
        user_id = f"bob-{uuid.uuid4().hex}"
        client.post("/check", json={"user_id": user_id, "cost": 10})

        response = client.post("/check", json={"user_id": user_id, "cost": 1})

        self.assertEqual(response.status_code, 429)
        self.assertFalse(response.json()["allowed"])


class AcquireReleaseEndpointTests(unittest.TestCase):
    def test_acquire_then_release(self):
        user_id = f"carol-{uuid.uuid4().hex}"

        acquire_response = client.post("/acquire", json={"user_id": user_id})
        self.assertEqual(acquire_response.status_code, 200)
        token = acquire_response.json()["token"]
        self.assertIsNotNone(token)

        release_response = client.post("/release", json={"token": token})
        self.assertTrue(release_response.json()["released"])

    def test_acquire_beyond_capacity_returns_429(self):
        user_id = f"dave-{uuid.uuid4().hex}"
        for _ in range(10):
            client.post("/acquire", json={"user_id": user_id})

        response = client.post("/acquire", json={"user_id": user_id})

        self.assertEqual(response.status_code, 429)
        self.assertFalse(response.json()["acquired"])


if __name__ == "__main__":
    unittest.main()
