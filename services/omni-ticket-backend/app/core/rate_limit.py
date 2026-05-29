import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request, status


@dataclass(frozen=True)
class RateLimitExceeded(Exception):
    retry_after_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        now: float | None = None,
    ) -> None:
        current_time = now or time.time()
        bucket = self._hits[key]
        cutoff = current_time - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, math.ceil(bucket[0] + window_seconds - current_time))
            raise RateLimitExceeded(retry_after)
        bucket.append(current_time)

    def reset(self) -> None:
        self._hits.clear()


rate_limiter = InMemoryRateLimiter()


def client_identity(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown-client"


def raise_rate_limit_exceeded(exc: RateLimitExceeded) -> None:
    raise HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded",
        headers={"Retry-After": str(exc.retry_after_seconds)},
    ) from exc
