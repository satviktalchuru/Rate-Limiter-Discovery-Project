import threading
import unittest
from unittest.mock import patch

from base import ConcurrencyLimiter, FixedWindowCounter, TokenBucket


class TokenBucketTests(unittest.TestCase):
    @patch("base.time.monotonic", return_value=0)
    def test_request_cost(self, clock):
        bucket = TokenBucket(capacity=5, refill_rate=1)

        result = bucket.allow("alice", cost=3)

        self.assertTrue(result.allowed)
        self.assertEqual(result.tokens_remaining, 2)

    @patch("base.time.monotonic", return_value=0)
    def test_tokens_refill_over_time(self, clock):
        bucket = TokenBucket(capacity=1, refill_rate=1)
        self.assertTrue(bucket.allow("alice").allowed)
        clock.return_value = 1
        self.assertTrue(bucket.allow("alice").allowed)

    @patch("base.time.monotonic", return_value=0)
    def test_rejected_request_returns_retry_time(self, clock):
        bucket = TokenBucket(capacity=2, refill_rate=1)
        bucket.allow("alice", cost=2)

        result = bucket.allow("alice")

        self.assertFalse(result.allowed)
        self.assertEqual(result.tokens_remaining, 0)
        self.assertEqual(result.retry_after, 1)

    @patch("base.time.monotonic", return_value=0)
    def test_concurrent_requests_never_exceed_capacity(self, clock):
        bucket = TokenBucket(capacity=10, refill_rate=1)
        results = []

        def worker():
            results.append(bucket.allow("alice").allowed)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(results.count(True), 10)


class FixedWindowCounterTests(unittest.TestCase):
    @patch("base.time.monotonic", return_value=0)
    def test_window_resets(self, clock):
        limiter = FixedWindowCounter(limit=1, window=10)
        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))
        clock.return_value = 10
        self.assertTrue(limiter.allow("alice"))

    @patch("base.time.monotonic", return_value=0)
    def test_concurrent_requests_never_exceed_limit(self, clock):
        limiter = FixedWindowCounter(limit=10, window=10)
        results = []

        def worker():
            results.append(limiter.allow("alice"))

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(results.count(True), 10)


class ConcurrencyLimiterTests(unittest.TestCase):
    def test_acquire_up_to_capacity_then_rejects(self):
        limiter = ConcurrencyLimiter(capacity=2)

        self.assertIsNotNone(limiter.acquire("job-a"))
        self.assertIsNotNone(limiter.acquire("job-a"))
        self.assertIsNone(limiter.acquire("job-a"))

    def test_release_frees_a_slot(self):
        limiter = ConcurrencyLimiter(capacity=1)
        token = limiter.acquire("job-a")

        limiter.release(token)

        self.assertIsNotNone(limiter.acquire("job-a"))

    def test_zero_capacity_is_invalid(self):
        with self.assertRaises(ValueError):
            ConcurrencyLimiter(capacity=0)

    def test_zero_lease_ttl_is_invalid(self):
        with self.assertRaises(ValueError):
            ConcurrencyLimiter(capacity=1, lease_ttl=0)

    @patch("base.time.monotonic", return_value=0)
    def test_expired_lease_is_freed_automatically(self, clock):
        limiter = ConcurrencyLimiter(capacity=1, lease_ttl=10)
        limiter.acquire("job-a")  # never released

        clock.return_value = 10
        self.assertIsNotNone(limiter.acquire("job-a"))

    def test_concurrent_acquires_never_exceed_capacity(self):
        limiter = ConcurrencyLimiter(capacity=10)
        results = []

        def worker():
            results.append(limiter.acquire("job-a") is not None)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(results.count(True), 10)


if __name__ == "__main__":
    unittest.main()
