import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    """In-memory limiter. Enough for a single API process in development."""

    def __init__(self, max_calls: int, window_seconds: int) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.monotonic()
        window_start = now - self.window_seconds
        recent = [stamp for stamp in self._hits[key] if stamp > window_start]
        if len(recent) >= self.max_calls:
            self._hits[key] = recent
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Try again shortly.",
            )
        recent.append(now)
        self._hits[key] = recent


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
