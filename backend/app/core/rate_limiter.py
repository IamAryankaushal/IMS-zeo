"""
Token-bucket rate limiter for signal ingestion.
Thread-safe, async-compatible.
"""
import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    capacity: int
    refill_rate: float  # tokens per second
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: asyncio.Lock = field(init=False)

    def __post_init__(self):
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """Return True if request is allowed, False if rate-limited."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self.capacity,
                self._tokens + elapsed * self.refill_rate
            )
            self._last_refill = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available(self) -> int:
        return int(self._tokens)


# Global ingestion rate limiter — one per process
_ingestion_limiter: TokenBucket | None = None


def get_rate_limiter(capacity: int = 10_000) -> TokenBucket:
    global _ingestion_limiter
    if _ingestion_limiter is None:
        _ingestion_limiter = TokenBucket(capacity=capacity, refill_rate=capacity)
    return _ingestion_limiter
