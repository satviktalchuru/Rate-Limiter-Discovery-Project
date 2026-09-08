import redis
from fastapi import FastAPI
from pydantic import BaseModel

from base import TokenBucket
from redis_limiter import RedisConcurrencyLimiter


app = FastAPI()
bucket = TokenBucket(capacity=10, refill_rate=2)
redis_client = redis.Redis(host="localhost", port=6379)
limiter = RedisConcurrencyLimiter(capacity=10, redis_client=redis_client)


class RequestData(BaseModel):
    user_id: str
    cost: float = 1


class JobRequest(BaseModel):
    user_id: str


@app.post("/check")
def check_rate_limit(request: RequestData):
    result = bucket.allow(request.user_id, request.cost)
    return {
        "allowed": result.allowed,
        "tokens_remaining": result.tokens_remaining,
        "retry_after": result.retry_after,
    }


@app.post("/acquire")
def acquire_slot(request: JobRequest):
    return {"acquired": limiter.acquire(request.user_id)}


@app.post("/release")
def release_slot(request: JobRequest):
    limiter.release(request.user_id)
    return {"released": True}
