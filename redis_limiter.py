import uuid
import redis
from base import RateLimitResult


class RedisConcurrencyLimiter:
    """Same acquire/release contract as ConcurrencyLimiter, but slot state
    lives in Redis instead of a Python dict -- multiple processes (or
    machines) share one view of who's holding a slot.

    acquire(key) returns a lease token (or None if full); release(token)
    frees it. A held slot expires on its own after lease_ttl seconds even
    if release() is never called, so a crashed caller doesn't leak a slot
    forever. Held leases are tracked as a Redis sorted set (member = lease
    token, score = expiry time); each Lua script below runs atomically
    inside Redis, replacing the threading.Lock the in-memory version uses.
    """

    _ACQUIRE_SCRIPT = """
    local redis_key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local ttl = tonumber(ARGV[2])
    local member = ARGV[3]

    local time_parts = redis.call('TIME')
    local now = tonumber(time_parts[1]) + tonumber(time_parts[2]) / 1000000

    redis.call('ZREMRANGEBYSCORE', redis_key, '-inf', now)
    local active = redis.call('ZCARD', redis_key)
    if active >= capacity then
        return 0
    end
    redis.call('ZADD', redis_key, now + ttl, member)
    redis.call('EXPIRE', redis_key, math.ceil(ttl) + 60)
    return 1
    """

    _RELEASE_SCRIPT = """
    return redis.call('ZREM', KEYS[1], ARGV[1])
    """

    def __init__(
        self,
        capacity: int,
        redis_client: redis.Redis,
        key_prefix: str = "concurrency_limiter",
        lease_ttl: float = 3600.0,
    ) -> None:
        if type(capacity) is not int:
            raise TypeError("capacity must be an integer")
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if lease_ttl <= 0:
            raise ValueError("lease_ttl must be positive")

        self.capacity = capacity
        self.key_prefix = key_prefix
        self.lease_ttl = lease_ttl
        self._redis = redis_client
        self._acquire_script = redis_client.register_script(self._ACQUIRE_SCRIPT)
        self._release_script = redis_client.register_script(self._RELEASE_SCRIPT)

    def _redis_key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def acquire(self, key: str) -> str | None:
        token = f"{key}:{uuid.uuid4().hex}"
        admitted = self._acquire_script(
            keys=[self._redis_key(key)],
            args=[self.capacity, self.lease_ttl, token],
        )
        return token if admitted else None

    def release(self, token: str) -> None:
        key, _, _ = token.partition(":")
        self._release_script(keys=[self._redis_key(key)], args=[token])


class RedisTokenBucket:
    """Same allow(key, cost) contract as TokenBucket, but token counts live
    in Redis so multiple processes share one real bucket per key instead of
    each holding its own in-memory copy. Refill math runs on Redis's own
    clock (TIME) rather than each caller's local clock, since clocks on
    different machines can't be trusted to agree with each other.
    """

    _ALLOW_SCRIPT = """
    local redis_key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local cost = tonumber(ARGV[3])

    local state = redis.call('HMGET', redis_key, 'tokens', 'last_refill')
    local time_parts = redis.call('TIME')
    local now = tonumber(time_parts[1]) + tonumber(time_parts[2]) / 1000000

    local tokens
    if state[1] == false then
        tokens = capacity
    else
        tokens = tonumber(state[1])
        local last_refill = tonumber(state[2])
        local elapsed = now - last_refill
        if elapsed > 0 then
            tokens = math.min(capacity, tokens + elapsed * refill_rate)
        end
    end

    if tokens < cost then
        redis.call('HMSET', redis_key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', redis_key, 3600)
        local missing = cost - tokens
        return {0, tostring(tokens), tostring(missing / refill_rate)}
    end

    tokens = tokens - cost
    redis.call('HMSET', redis_key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', redis_key, 3600)
    return {1, tostring(tokens), "0"}
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        redis_client: redis.Redis,
        key_prefix: str = "token_bucket",
    ) -> None:
        if capacity <= 0 or refill_rate <= 0:
            raise ValueError("capacity and refill_rate must be positive")

        self.capacity = capacity
        self.refill_rate = refill_rate
        self.key_prefix = key_prefix
        self._redis = redis_client
        self._allow_script = redis_client.register_script(self._ALLOW_SCRIPT)

    def _redis_key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def allow(self, key: str, cost: float = 1) -> RateLimitResult:
        if cost <= 0 or cost > self.capacity:
            raise ValueError("cost must be between 0 and capacity")

        allowed, tokens_remaining, retry_after = self._allow_script(
            keys=[self._redis_key(key)],
            args=[self.capacity, self.refill_rate, cost],
        )
        return RateLimitResult(
            allowed=bool(allowed),
            tokens_remaining=float(tokens_remaining),
            retry_after=float(retry_after),
        )
