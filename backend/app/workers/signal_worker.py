"""
Background queue worker.
Drains the in-memory asyncio.Queue and persists signals to storage.
Provides backpressure: if DBs are slow, signals queue up in memory.
Also emits throughput metrics every 5 seconds.
"""
import asyncio
import logging
import time
from typing import Any

from app.core.config import get_settings
from app.core.queue import get_signal_queue
from app.db.connections import AsyncSessionFactory
from app.services.signal_service import (
    find_or_create_work_item,
    get_debounce,
    invalidate_dashboard_cache,
    link_signal_to_work_item,
    store_raw_signal,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Throughput counters
_processed_count = 0
_dropped_count = 0
_metrics_start = time.monotonic()


async def _process_one(signal: dict[str, Any]) -> None:
    """Process a single signal end-to-end with retry logic."""
    global _processed_count

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 1. Store raw signal to MongoDB (audit log)
            signal_id = await store_raw_signal(signal)

            # 2. Check debounce window
            debounce = get_debounce()
            should_create, count = await debounce.record(
                signal["component_id"], signal_id
            )

            # 3. Create/update work item in PostgreSQL (transactional)
            async with AsyncSessionFactory() as session:
                async with session.begin():
                    work_item_id, was_created = await find_or_create_work_item(
                        session, signal
                    )

            # 4. Link signal → work item in MongoDB
            await link_signal_to_work_item(signal_id, work_item_id)

            # 5. Invalidate Redis cache
            await invalidate_dashboard_cache(work_item_id)

            _processed_count += 1
            return

        except Exception as exc:
            if attempt < max_retries - 1:
                wait = 0.1 * (2 ** attempt)  # exponential backoff: 0.1s, 0.2s
                logger.warning(
                    "Signal processing attempt %d/%d failed (%s). Retrying in %.1fs",
                    attempt + 1, max_retries, exc, wait
                )
                await asyncio.sleep(wait)
            else:
                logger.error(
                    "Signal processing failed after %d attempts: %s | signal=%s",
                    max_retries, exc, signal.get("component_id")
                )


async def _emit_metrics(queue: asyncio.Queue) -> None:
    """Print throughput metrics every N seconds."""
    global _processed_count, _metrics_start

    while True:
        await asyncio.sleep(settings.metrics_interval_seconds)
        elapsed = time.monotonic() - _metrics_start
        rate = _processed_count / elapsed if elapsed > 0 else 0
        logger.info(
            "📊 METRICS | processed=%d | rate=%.1f sig/s | queue=%d/%d | dropped=%d",
            _processed_count, rate, queue.qsize(), queue.maxsize, _dropped_count
        )


async def run_worker(concurrency: int = 20) -> None:
    """
    Main worker loop. Uses a semaphore to bound concurrent DB operations
    while keeping throughput high.
    """
    queue = get_signal_queue(settings.queue_max_size)
    semaphore = asyncio.Semaphore(concurrency)

    # Start metrics emitter as background task
    asyncio.create_task(_emit_metrics(queue))

    logger.info("Signal worker started (concurrency=%d)", concurrency)

    async def bounded_process(signal: dict[str, Any]) -> None:
        async with semaphore:
            await _process_one(signal)

    while True:
        signal = await queue.get()
        asyncio.create_task(bounded_process(signal))
        queue.task_done()
