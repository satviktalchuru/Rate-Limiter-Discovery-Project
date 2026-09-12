#Fire job requests at a limiter and report how many were admitted. 

import argparse
import threading
import time


def build_limiter(args: argparse.Namespace):
    from base import ConcurrencyLimiter, TokenBucket

    if args.algorithm == "token_bucket":
        return TokenBucket(capacity=args.capacity, refill_rate=args.refill_rate)
    if args.algorithm == "concurrency":
        return ConcurrencyLimiter(capacity=args.capacity)
    if args.algorithm == "redis_concurrency":
        import redis

        from redis_limiter import RedisConcurrencyLimiter

        client = redis.Redis(host="localhost", port=6379)
        return RedisConcurrencyLimiter(
            capacity=args.capacity,
            redis_client=client,
            key_prefix=f"loadtest:{time.time()}",
        )
    raise ValueError(f"unknown algorithm: {args.algorithm}")


def fire_burst(limiter, args: argparse.Namespace) -> list[bool]:
    results: list[bool] = []
    results_lock = threading.Lock()
    start_gate = threading.Barrier(args.clients)

    def worker() -> None:
        start_gate.wait()  # line every client up so they all fire together
        if args.algorithm == "token_bucket":
            admitted = limiter.allow(args.key, args.cost).allowed
        else:
            admitted = limiter.acquire(args.key)
        with results_lock:
            results.append(admitted)

    threads = [threading.Thread(target=worker) for _ in range(args.clients)]
    started_at = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.perf_counter() - started_at

    print(f"algorithm={args.algorithm} capacity={args.capacity} clients={args.clients}")
    print(f"admitted={results.count(True)} rejected={results.count(False)} elapsed={elapsed:.4f}s")
    return results


def fire_staggered(limiter, args: argparse.Namespace) -> list[bool]:
    results: list[bool] = []
    started_at = time.perf_counter()

    for i in range(args.clients):
        if args.algorithm == "token_bucket":
            admitted = limiter.allow(args.key, args.cost).allowed
        else:
            admitted = limiter.acquire(args.key)
        results.append(admitted)
        print(f"t={time.perf_counter() - started_at:6.2f}s admitted={admitted}")
        if i < args.clients - 1:
            time.sleep(args.interval)

    print(f"algorithm={args.algorithm} capacity={args.capacity} clients={args.clients} interval={args.interval}s")
    print(f"admitted={results.count(True)} rejected={results.count(False)}")
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--algorithm", choices=["token_bucket", "concurrency", "redis_concurrency"], default="concurrency")
    parser.add_argument("--capacity", type=int, default=10)
    parser.add_argument("--refill-rate", type=float, default=2.0, help="token_bucket only")
    parser.add_argument("--cost", type=float, default=1.0, help="token_bucket only")
    parser.add_argument("--clients", type=int, default=50, help="simulated jobs, all competing for one key")
    parser.add_argument("--key", default="gpu-pool", help="shared key all simulated clients contend for")
    parser.add_argument(
        "--interval",
        type=float,
        default=0.0,
        help="seconds to wait between each client's request; 0 fires everyone at once (a burst)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    parsed_args = parse_args()
    built_limiter = build_limiter(parsed_args)
    if parsed_args.interval > 0:
        fire_staggered(built_limiter, parsed_args)
    else:
        fire_burst(built_limiter, parsed_args)
