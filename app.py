from fastapi import FastAPI
from pydantic import BaseModel

from base import TokenBucket


app = FastAPI()
bucket = TokenBucket(capacity=10, refill_rate=2)


class RequestData(BaseModel):
    user_id: str
    cost: float = 1


@app.post("/check")
def check_rate_limit(request: RequestData):
    result = bucket.allow(request.user_id, request.cost)
    return {
        "allowed": result.allowed,
        "tokens_remaining": result.tokens_remaining,
        "retry_after": result.retry_after,
    }
