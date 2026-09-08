import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass


class Algorithm(ABC):
    @abstractmethod
    def allow(self, key: str) -> bool:
        """Return whether request identified by key allowed."""


# Fixed-window counter algorithm
class FixedWindowCounter(Algorithm):
    def __init__(self, limit: int, window: int) -> None:
        if type(limit) is not int or type(window) is not int:
            raise TypeError("limit and window must be integers")
        if limit <= 0 or window <= 0:
            raise ValueError("limit and window must be positive")

        self.limit = limit
        self.window = window
        self.perkey_state: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        with self._lock:
            now = time.monotonic()
            state = self.perkey_state.get(key)

            if state is None or (now - state["window_start"]) >= self.window:
                self.perkey_state[key] = {"count": 1, "window_start": now}
                return True

            if state["count"] >= self.limit:
                return False

            self.perkey_state[key] = {
                "count": state["count"] + 1,
                "window_start": state["window_start"],
            }
            return True


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    tokens_remaining: float
    retry_after: float


class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float) -> None:
        if capacity <= 0 or refill_rate <= 0:
            raise ValueError("capacity and refill_rate must be positive")

        self.capacity = capacity
        self.refill_rate = refill_rate  # Tokens added per second.
        self.perkey_state: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, cost: float = 1) -> RateLimitResult:
        if cost <= 0 or cost > self.capacity:
            raise ValueError("cost must be between 0 and capacity")

        with self._lock:
            now = time.monotonic()
            state = self.perkey_state.get(key)
            if state is None:
                state = {"tokens": float(self.capacity), "last_refill": now}
                self.perkey_state[key] = state

            # Refilling when a request arrives
            elapsed = now - state["last_refill"]
            state["tokens"] = min(self.capacity, state["tokens"] + elapsed * self.refill_rate)
            state["last_refill"] = now

            if state["tokens"] < cost:
                missing_tokens = cost - state["tokens"]
                return RateLimitResult(
                    allowed=False,
                    tokens_remaining=state["tokens"],
                    retry_after=missing_tokens / self.refill_rate,
                )

            state["tokens"] -= cost
            return RateLimitResult(
                allowed=True,
                tokens_remaining=state["tokens"],
                retry_after=0.0,
            )


class ConcurrencyLimiter:
    """Limits how many slots a key can hold at a time."""

    def __init__(self, capacity: int) -> None:
        if type(capacity) is not int:
            raise TypeError("capacity must be an integer")
        if capacity <= 0:
            raise ValueError("capacity must be positive")

        self.capacity = capacity
        self.perkey_active: dict[str, int] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str) -> bool:
        with self._lock:
            active = self.perkey_active.get(key, 0)
            if active >= self.capacity:
                return False
            self.perkey_active[key] = active + 1
            return True

    def release(self, key: str) -> None:
        with self._lock:
            active = self.perkey_active.get(key, 0)
            if active <= 0:
                return
            if active == 1:
                del self.perkey_active[key]
            else:
                self.perkey_active[key] = active - 1
