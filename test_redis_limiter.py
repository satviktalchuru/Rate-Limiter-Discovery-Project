import threading
import unittest
import uuid

import redis

from redis_limiter import RedisConcurrencyLimiter


class RedisConcurrencyLimiterTests(unittest.TestCase):
    """Requires a real Redis instance at localhost:6379 (see README)."""

    def setUp(self) -> None:
        self.redis_client = redis.Redis(host="localhost", port=6379, db=0)
        self.key_prefix = f"test:{uuid.uuid4()}"

    def tearDown(self) -> None:
        for key in self.redis_client.keys(f"{self.key_prefix}:*"):
            self.redis_client.delete(key)

    def make_limiter(self, capacity: int) -> RedisConcurrencyLimiter:
        return RedisConcurrencyLimiter(
            capacity=capacity,
            redis_client=self.redis_client,
            key_prefix=self.key_prefix,
        )

    def test_acquire_up_to_capacity_then_rejects(self):
        limiter = self.make_limiter(capacity=2)

        self.assertTrue(limiter.acquire("job-a"))
        self.assertTrue(limiter.acquire("job-a"))
        self.assertFalse(limiter.acquire("job-a"))

    def test_release_frees_a_slot(self):
        limiter = self.make_limiter(capacity=1)
        limiter.acquire("job-a")

        limiter.release("job-a")

        self.assertTrue(limiter.acquire("job-a"))

    def test_zero_capacity_is_invalid(self):
        with self.assertRaises(ValueError):
            self.make_limiter(capacity=0)

    def test_concurrent_acquires_never_exceed_capacity(self):
        limiter = self.make_limiter(capacity=10)
        results = []

        def worker():
            results.append(limiter.acquire("job-a"))

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(results.count(True), 10)


if __name__ == "__main__":
    unittest.main()
