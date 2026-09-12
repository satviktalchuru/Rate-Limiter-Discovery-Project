# Rate Limiter Discovery Project

I'm building this from scratch to learn how rate limiters actually work,
using a GPU-workload angle. There are three algorithms: a fixed window
counter, a token bucket (where tokens refill over time and each request costs
tokens), and a concurrency limiter (which holds a position until we release it). There's also a Redis-backed version of the concurrency limiter, so multiple processes can share one real count instead of each having their own.

A FastAPI app wraps these into three endpoints, both Redis-backed:
`/check` (token bucket), and `/acquire` / `/release` (
`/acquire` hands back a token, which you send to `/release` later).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Redis needs to be running locally before you start the API or run the tests:

```bash
docker run -d --name rate-limiter-redis -p 6379:6379 redis:7-alpine
```

Run the API:

```bash
uvicorn app:app --reload
```

Run all the tests:

```bash
python3 -m unittest discover
```

Try different rate-limit configs without touching the server:

```bash
python3 loadtest.py --algorithm concurrency --capacity 8 --clients 20
```
