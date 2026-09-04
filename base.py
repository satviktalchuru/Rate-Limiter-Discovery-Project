import time
from abc import ABC, abstractmethod


class Algorithm(ABC):
    def __init__(self, limit: int, window: int) -> None:
        if type(limit) is not int or type(window) is not int:
            raise TypeError("limit and window must be integers")
        if limit <= 0 or window <= 0:
            raise ValueError("limit and window must be positive")

        self.limit = limit
        self.window = window

    @abstractmethod
    def allow(self, key: str) -> bool:
        """Return whether request identified by key allowed."""

#fixed window counter algorithm
class FixedWindowCounter(Algorithm):
    def __init__(self, limit: int, window: int) -> None:
        super().__init__(limit, window)
        self.perkey_state: dict[str, dict[str, float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
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

