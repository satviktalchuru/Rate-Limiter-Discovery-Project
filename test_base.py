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


class FixedWindowCounterTests(unittest.TestCase):
    @patch("base.time.monotonic", return_value=0)
    def test_window_resets(self, clock):
        limiter = FixedWindowCounter(limit=1, window=10)
        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))
        clock.return_value = 10
        self.assertTrue(limiter.allow("alice"))


class ConcurrencyLimiterTests(unittest.TestCase):
    def test_acquire_up_to_capacity_then_rejects(self):
        limiter = ConcurrencyLimiter(capacity=2)

        self.assertTrue(limiter.acquire("job-a"))
        self.assertTrue(limiter.acquire("job-a"))
        self.assertFalse(limiter.acquire("job-a"))

    def test_release_frees_a_slot(self):
        limiter = ConcurrencyLimiter(capacity=1)
        limiter.acquire("job-a")

        limiter.release("job-a")

        self.assertTrue(limiter.acquire("job-a"))

    def test_zero_capacity_is_invalid(self):
        with self.assertRaises(ValueError):
            ConcurrencyLimiter(capacity=0)

    def test_concurrent_acquires_never_exceed_capacity(self):
        limiter = ConcurrencyLimiter(capacity=10)
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
