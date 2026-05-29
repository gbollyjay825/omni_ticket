from datetime import UTC, datetime
from math import ceil

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.rate_limit import RateLimitExceeded
from app.db.models import RateLimitRecord
from app.models.domain import utc_now


def _aware(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp


class DatabaseRateLimiter:
    def check(self, db: Session, key: str, *, limit: int, window_seconds: int) -> None:
        if self._attempt_check(db, key, limit=limit, window_seconds=window_seconds):
            return
        self._attempt_check(db, key, limit=limit, window_seconds=window_seconds)

    def _attempt_check(self, db: Session, key: str, *, limit: int, window_seconds: int) -> bool:
        now = utc_now()
        record = db.get(RateLimitRecord, key)
        if record is None:
            db.add(RateLimitRecord(key=key, window_start=now, count=1))
            try:
                db.commit()
                return True
            except IntegrityError:
                db.rollback()
                return False

        elapsed = (now - _aware(record.window_start)).total_seconds()
        if elapsed >= window_seconds:
            record.window_start = now
            record.count = 1
            db.commit()
            return True

        if record.count >= limit:
            retry_after = max(1, ceil(window_seconds - elapsed))
            raise RateLimitExceeded(retry_after)

        record.count += 1
        db.commit()
        return True


database_rate_limiter = DatabaseRateLimiter()
