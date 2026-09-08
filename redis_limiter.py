import redis


class RedisConcurrencyLimiter:
    """Same acquire/release contract as ConcurrencyLimiter, but slot counts
    live in Redis instead of a Python dict -- multiple processes (or
    machines) share one view of how many slots are held per key, instead
    of each holding its own in-memory copy.

    Each Lua script below runs atomically inside Redis, which replaces the
    threading.Lock ConcurrencyLimiter uses to guard its read-modify-write.
    """

    _ACQUIRE_SCRIPT = """
    local current = tonumber(redis.call('GET', KEYS[1]) or '0')
    if current >= tonumber(ARGV[1]) then
        return 0
    end
    redis.call('INCR', KEYS[1])
    return 1
    """

    _RELEASE_SCRIPT = """
    local current = tonumber(redis.call('GET', KEYS[1]) or '0')
    if current <= 0 then
        return 0
    end
    redis.call('DECR', KEYS[1])
    return 1
    """

    def __init__(
        self,
        capacity: int,
        redis_client: redis.Redis,
        key_prefix: str = "concurrency_limiter",
    ) -> None:
        if type(capacity) is not int:
            raise TypeError("capacity must be an integer")
        if capacity <= 0:
            raise ValueError("capacity must be positive")

        self.capacity = capacity
        self.key_prefix = key_prefix
        self._redis = redis_client
        self._acquire_script = redis_client.register_script(self._ACQUIRE_SCRIPT)
        self._release_script = redis_client.register_script(self._RELEASE_SCRIPT)

    def _redis_key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def acquire(self, key: str) -> bool:
        result = self._acquire_script(keys=[self._redis_key(key)], args=[self.capacity])
        return bool(result)

    def release(self, key: str) -> None:
        self._release_script(keys=[self._redis_key(key)], args=[])
