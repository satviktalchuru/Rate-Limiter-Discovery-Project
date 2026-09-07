import unittest
from unittest.mock import patch

from base import FixedWindowCounter, TokenBucket


class ClockTests(unittest.TestCase):
    def setUp(self) -> None:
        clock_patch = patch("base.time.monotonic", return_value=100.0)
        self.clock = clock_patch.start()
        self.addCleanup(clock_patch.stop)


class FixedWindowCounterTests(ClockTests):
    def test_limits_each_key_independently(self) -> None:
        limiter = FixedWindowCounter(limit=2, window=60)

        self.assertTrue(limiter.allow("alice"))
        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))
        self.assertTrue(limiter.allow("bob"))


class TokenBucketTests(ClockTests):
    def test_initial_burst_and_independent_users(self) -> None:
        limiter = TokenBucket(2, 60)
        self.assertTrue(limiter.allow("alice"))
        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))
        self.assertTrue(limiter.allow("bob"))

    def test_fractional_refill_survives_rejected_requests(self) -> None:
        limiter = TokenBucket(2, 60)
        limiter.allow("alice")
        limiter.allow("alice")
        self.clock.return_value = 115.0
        self.assertFalse(limiter.allow("alice"))
        self.clock.return_value = 130.0
        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))

    def test_refill_is_capped_at_capacity(self) -> None:
        limiter = TokenBucket(2, 60)
        limiter.allow("alice")
        limiter.allow("alice")
        self.clock.return_value = 1000.0
        self.assertTrue(limiter.allow("alice"))
        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))

    def test_invalid_configuration(self) -> None:
        for limit, window, error in [(0, 60, ValueError), (2, -1, ValueError),
                                      (True, 60, TypeError), (2, 1.5, TypeError)]:
            with self.subTest(limit=limit, window=window):
                with self.assertRaises(error):
                    TokenBucket(limit, window)


if __name__ == "__main__":
    unittest.main()
