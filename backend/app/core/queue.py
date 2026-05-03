"""
In-memory bounded async queue for signal ingestion.
Provides backpressure: if the persistence layer is slow,
signals are buffered here rather than crashing or blocking the HTTP layer.
"""
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

_signal_queue: asyncio.Queue | None = None


def get_signal_queue(max_size: int = 50_000) -> asyncio.Queue:
    """Get (or create) the singleton signal queue."""
    global _signal_queue
    if _signal_queue is None:
        _signal_queue = asyncio.Queue(maxsize=max_size)
        logger.info("Signal queue initialised (max_size=%d)", max_size)
    return _signal_queue


async def enqueue_signal(signal: dict[str, Any], queue: asyncio.Queue) -> bool:
    """
    Non-blocking enqueue. Returns False (drops signal) if queue is full
    rather than blocking the ingestion API.
    """
    try:
        queue.put_nowait(signal)
        return True
    except asyncio.QueueFull:
        logger.warning("Signal queue full — dropping signal for component=%s", signal.get("component_id"))
        return False
