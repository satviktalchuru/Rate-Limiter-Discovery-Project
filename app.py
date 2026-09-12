import redis
from fastapi import FastAPI, Response, status
from pydantic import BaseModel

from redis_limiter import RedisConcurrencyLimiter, RedisTokenBucket


app = FastAPI()
redis_client = redis.Redis(host="localhost", port=6379)
bucket = RedisTokenBucket(capacity=10, refill_rate=2, redis_client=redis_client)
limiter = RedisConcurrencyLimiter(capacity=10, redis_client=redis_client)


class RequestData(BaseModel):
    user_id: str
    cost: float = 1


class AcquireRequest(BaseModel):
    user_id: str


class ReleaseRequest(BaseModel):
    token: str


@app.post("/check")
def check_rate_limit(request: RequestData, response: Response):
    result = bucket.allow(request.user_id, request.cost)
    if not result.allowed:
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
    return {
        "allowed": result.allowed,
        "tokens_remaining": result.tokens_remaining,
        "retry_after": result.retry_after,
    }


@app.post("/acquire")
def acquire_slot(request: AcquireRequest, response: Response):
    token = limiter.acquire(request.user_id)
    if token is None:
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
    return {"acquired": token is not None, "token": token}


@app.post("/release")
def release_slot(request: ReleaseRequest):
    limiter.release(request.token)
    return {"released": True}
