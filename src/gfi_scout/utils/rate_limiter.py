"""Simple async token-bucket rate limiter.

Used to cap outgoing GitHub API calls so we don't blow through the 5,000/hr
authenticated quota when a heavy `find_issues` query touches many repos.
"""

from __future__ import annotations

import asyncio
import time
from types import TracebackType
from typing import Self


class RateLimiter:
    """Async token-bucket limiter.

    Allows up to `rate` events per `per` seconds. Callers `await limiter.acquire()`
    before issuing a request; the call blocks just long enough for a token
    to become available.
    """

    def __init__(self, *, rate: float, per: float = 1.0) -> None:
        if rate <= 0 or per <= 0:
            raise ValueError("rate and per must be positive")
        self._capacity = rate
        self._tokens = rate
        self._fill_rate = rate / per
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    self._capacity, self._tokens + elapsed * self._fill_rate,
                )
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._fill_rate
                await asyncio.sleep(wait)

    async def __aenter__(self) -> Self:
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None
