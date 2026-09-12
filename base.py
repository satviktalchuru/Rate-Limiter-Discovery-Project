import threading
import time
import uuid
from dataclasses import dataclass


# Fixed-window counter algorithm
class FixedWindowCounter:
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
    #Limits how many slots a key can hold at a time.
    #acquire(key) returns a lease token, #release(token) frees that slot. 

    def __init__(self, capacity: int, lease_ttl: float = 3600.0) -> None:
        if type(capacity) is not int:
            raise TypeError("capacity must be an integer")
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if lease_ttl <= 0:
            raise ValueError("lease_ttl must be positive")

        self.capacity = capacity
        self.lease_ttl = lease_ttl
        self.perkey_leases: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str) -> str | None:
        with self._lock:
            now = time.monotonic()
            leases = self.perkey_leases.setdefault(key, {})

            expired = [token for token, expires_at in leases.items() if expires_at <= now]
            for token in expired:
                del leases[token]

            if len(leases) >= self.capacity:
                if not leases:
                    del self.perkey_leases[key]
                return None

            token = f"{key}:{uuid.uuid4().hex}"
            leases[token] = now + self.lease_ttl
            return token

    def release(self, token: str) -> None:
        with self._lock:
            key, _, _ = token.partition(":")
            leases = self.perkey_leases.get(key)
            if leases is None:
                return
            leases.pop(token, None)
            if not leases:
                del self.perkey_leases[key]
