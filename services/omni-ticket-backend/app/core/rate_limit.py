from dataclasses import dataclass

from fastapi import HTTPException, Request, status


@dataclass(frozen=True)
class RateLimitExceeded(Exception):
    retry_after_seconds: int


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
