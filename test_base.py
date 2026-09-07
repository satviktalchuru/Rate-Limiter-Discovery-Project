import unittest
from unittest.mock import patch

from base import FixedWindowCounter, TokenBucket


class TokenBucketTests(unittest.TestCase):
    @patch("base.time.monotonic", return_value=0)
    def test_bucket_starts_full(self, clock):
        bucket = TokenBucket(capacity=2, refill_rate=1)
        self.assertTrue(bucket.allow("alice"))
        self.assertTrue(bucket.allow("alice"))
        self.assertFalse(bucket.allow("alice"))

    @patch("base.time.monotonic", return_value=0)
    def test_each_user_has_their_own_bucket(self, clock):
        bucket = TokenBucket(capacity=1, refill_rate=1)
        self.assertTrue(bucket.allow("alice"))
        self.assertFalse(bucket.allow("alice"))
        self.assertTrue(bucket.allow("bob"))

    @patch("base.time.monotonic", return_value=0)
    def test_tokens_refill_over_time(self, clock):
        bucket = TokenBucket(capacity=1, refill_rate=0.5)
        self.assertTrue(bucket.allow("alice"))
        clock.return_value = 1  # Half a token: still too little.
        self.assertFalse(bucket.allow("alice"))
        clock.return_value = 2  # One full token is now available.
        self.assertTrue(bucket.allow("alice"))
        self.assertFalse(bucket.allow("alice"))

    @patch("base.time.monotonic", return_value=0)
    def test_bucket_cannot_overfill(self, clock):
        bucket = TokenBucket(capacity=2, refill_rate=1)
        bucket.allow("alice")
        bucket.allow("alice")
        clock.return_value = 100
        self.assertTrue(bucket.allow("alice"))
        self.assertTrue(bucket.allow("alice"))
        self.assertFalse(bucket.allow("alice"))

    def test_zero_capacity_is_invalid(self):
        with self.assertRaises(ValueError):
            TokenBucket(capacity=0, refill_rate=1)

    def test_zero_refill_rate_is_invalid(self):
        with self.assertRaises(ValueError):
            TokenBucket(capacity=2, refill_rate=0)


class FixedWindowCounterTests(unittest.TestCase):
    @patch("base.time.monotonic", return_value=0)
    def test_window_resets(self, clock):
        limiter = FixedWindowCounter(limit=1, window=10)
        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))
        clock.return_value = 10
        self.assertTrue(limiter.allow("alice"))


if __name__ == "__main__":
    unittest.main()
