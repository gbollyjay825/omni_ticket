from __future__ import annotations

from contextvars import ContextVar
import json
import logging
import re
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
PROCESS_TIME_HEADER = "X-Process-Time-Ms"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_request_id: ContextVar[str | None] = ContextVar("omni_request_id", default=None)
access_logger = logging.getLogger("omni_ticket.access")
access_logger.setLevel(logging.INFO)


def current_request_id() -> str | None:
    return _request_id.get()


def normalize_request_id(raw_request_id: str | None) -> str:
    if raw_request_id:
        candidate = raw_request_id.strip()
        if _REQUEST_ID_PATTERN.fullmatch(candidate):
            return candidate
    return f"req_{uuid4().hex}"


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = _request_id.set(request_id)
        started_at = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            self._log_request(request, request_id, status_code, started_at, error=exc)
            raise
        finally:
            if "response" in locals():
                elapsed_ms = self._elapsed_ms(started_at)
                response.headers[REQUEST_ID_HEADER] = request_id
                response.headers[PROCESS_TIME_HEADER] = f"{elapsed_ms:.2f}"
                self._log_request(request, request_id, status_code, started_at)
            _request_id.reset(token)

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return (perf_counter() - started_at) * 1000

    def _log_request(
        self,
        request: Request,
        request_id: str,
        status_code: int,
        started_at: float,
        *,
        error: Exception | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "event": "http.request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": round(self._elapsed_ms(started_at), 2),
        }
        if error is not None:
            payload["error_type"] = type(error).__name__
        access_logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True))
