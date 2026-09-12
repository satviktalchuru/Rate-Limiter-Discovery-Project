import threading
import time
import unittest
import uuid

import redis

from redis_limiter import RedisConcurrencyLimiter, RedisTokenBucket


class RedisConcurrencyLimiterTests(unittest.TestCase):
    #Requires a real Redis instance at localhost:6379

    def setUp(self) -> None:
        self.redis_client = redis.Redis(host="localhost", port=6379, db=0)
        self.key_prefix = f"test:{uuid.uuid4()}"

    def tearDown(self) -> None:
        for key in self.redis_client.keys(f"{self.key_prefix}:*"):
            self.redis_client.delete(key)

    def make_limiter(self, capacity: int, lease_ttl: float = 3600.0) -> RedisConcurrencyLimiter:
        return RedisConcurrencyLimiter(
            capacity=capacity,
            redis_client=self.redis_client,
            key_prefix=self.key_prefix,
            lease_ttl=lease_ttl,
        )

    def test_acquire_up_to_capacity_then_rejects(self):
        limiter = self.make_limiter(capacity=2)

        self.assertIsNotNone(limiter.acquire("job-a"))
        self.assertIsNotNone(limiter.acquire("job-a"))
        self.assertIsNone(limiter.acquire("job-a"))

    def test_release_frees_a_slot(self):
        limiter = self.make_limiter(capacity=1)
        token = limiter.acquire("job-a")

        limiter.release(token)

        self.assertIsNotNone(limiter.acquire("job-a"))

    def test_zero_capacity_is_invalid(self):
        with self.assertRaises(ValueError):
            self.make_limiter(capacity=0)

    def test_expired_lease_is_freed_automatically(self):
        limiter = self.make_limiter(capacity=1, lease_ttl=0.3)
        limiter.acquire("job-a")  # never released

        time.sleep(0.4)

        self.assertIsNotNone(limiter.acquire("job-a"))

    def test_concurrent_acquires_never_exceed_capacity(self):
        limiter = self.make_limiter(capacity=10)
        results = []

        def worker():
            results.append(limiter.acquire("job-a") is not None)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(results.count(True), 10)


class RedisTokenBucketTests(unittest.TestCase):
    #Requires a real Redis instance at localhost:6379

    def setUp(self) -> None:
        self.redis_client = redis.Redis(host="localhost", port=6379, db=0)
        self.key_prefix = f"test:{uuid.uuid4()}"

    def tearDown(self) -> None:
        for key in self.redis_client.keys(f"{self.key_prefix}:*"):
            self.redis_client.delete(key)

    def make_bucket(self, capacity: int, refill_rate: float) -> RedisTokenBucket:
        return RedisTokenBucket(
            capacity=capacity,
            refill_rate=refill_rate,
            redis_client=self.redis_client,
            key_prefix=self.key_prefix,
        )

    def test_request_cost(self):
        bucket = self.make_bucket(capacity=5, refill_rate=1)

        result = bucket.allow("alice", cost=3)

        self.assertTrue(result.allowed)
        self.assertEqual(result.tokens_remaining, 2)

    def test_rejected_request_returns_retry_after(self):
        bucket = self.make_bucket(capacity=2, refill_rate=1)
        bucket.allow("alice", cost=2)

        result = bucket.allow("alice")

        self.assertFalse(result.allowed)
        self.assertAlmostEqual(result.tokens_remaining, 0, delta=0.05)
        self.assertAlmostEqual(result.retry_after, 1, delta=0.05)

    def test_zero_capacity_is_invalid(self):
        with self.assertRaises(ValueError):
            self.make_bucket(capacity=0, refill_rate=1)


if __name__ == "__main__":
    unittest.main()
