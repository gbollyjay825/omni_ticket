from dataclasses import dataclass

from fastapi import HTTPException, status


@dataclass(frozen=True)
class RateLimitExceeded(Exception):
    retry_after_seconds: int


def raise_rate_limit_exceeded(exc: RateLimitExceeded) -> None:
    raise HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded",
        headers={"Retry-After": str(exc.retry_after_seconds)},
    ) from exc
