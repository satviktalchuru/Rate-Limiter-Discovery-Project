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
    
