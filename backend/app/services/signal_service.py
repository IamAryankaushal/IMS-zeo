"""
Signal processing service.
Handles debounce logic: 100 signals for the same component within 10s
→ one WorkItem, all signals linked in MongoDB.
"""
import asyncio
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.alert_strategy import AlertContext, resolve_strategy
from app.core.config import get_settings
from app.db.connections import get_mongo_db, get_redis
from app.models.orm import WorkItem

logger = logging.getLogger(__name__)
settings = get_settings()


class DebounceWindow:
    """Tracks signals per component within a rolling time window."""

    def __init__(self, window_seconds: int, threshold: int):
        self.window = window_seconds
        self.threshold = threshold
        # component_id → list of (timestamp, signal_id)
        self._buckets: dict[str, list[tuple[float, str]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def record(self, component_id: str, signal_id: str) -> tuple[bool, int]:
        """
        Record a signal. Returns (should_create_work_item, count_in_window).
        should_create_work_item is True only when count crosses threshold.
        """
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window
            bucket = self._buckets[component_id]
            # evict old entries
            self._buckets[component_id] = [(ts, sid) for ts, sid in bucket if ts > cutoff]
            self._buckets[component_id].append((now, signal_id))
            count = len(self._buckets[component_id])
            # Fire exactly when we cross the threshold
            return (count == self.threshold), count


_debounce: DebounceWindow | None = None


def get_debounce() -> DebounceWindow:
    global _debounce
    if _debounce is None:
        _debounce = DebounceWindow(
            window_seconds=settings.debounce_window_seconds,
            threshold=settings.debounce_threshold,
        )
    return _debounce


async def store_raw_signal(signal: dict[str, Any]) -> str:
    """Persist raw signal to MongoDB. Returns the inserted document ID."""
    db = get_mongo_db()
    signal["_inserted_at"] = datetime.now(timezone.utc)
    result = await db.signals.insert_one(signal)
    return str(result.inserted_id)


async def find_or_create_work_item(
    session: AsyncSession,
    signal: dict[str, Any],
) -> tuple[str, bool]:
    """
    Find an existing OPEN/INVESTIGATING work item for this component,
    or create a new one. Returns (work_item_id, was_created).
    """
    component_id = signal["component_id"]

    # Look for an active work item
    stmt = (
        select(WorkItem)
        .where(WorkItem.component_id == component_id)
        .where(WorkItem.status.in_(["OPEN", "INVESTIGATING"]))
        .order_by(WorkItem.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # Increment signal count + update last_signal_at
        await session.execute(
            update(WorkItem)
            .where(WorkItem.id == existing.id)
            .values(
                signal_count=WorkItem.signal_count + 1,
                last_signal_at=datetime.now(timezone.utc),
            )
        )
        return str(existing.id), False

    # Create new work item using the strategy pattern
    strategy = resolve_strategy(component_id)
    ctx = AlertContext(
        component_id=component_id,
        component_type=signal.get("component_type", "UNKNOWN"),
        signal_count=1,
        error_type=signal.get("error_type", "UNKNOWN"),
    )
    priority = strategy.get_priority(ctx)
    title = strategy.get_title(ctx)
    strategy.notify(ctx, priority)

    work_item = WorkItem(
        id=uuid.uuid4(),
        component_id=component_id,
        title=title,
        status="OPEN",
        priority=priority,
        signal_count=1,
        first_signal_at=signal.get("timestamp") or datetime.now(timezone.utc),
        last_signal_at=datetime.now(timezone.utc),
    )
    session.add(work_item)
    await session.flush()
    return str(work_item.id), True


async def link_signal_to_work_item(signal_id: str, work_item_id: str) -> None:
    """Update the MongoDB signal document with the work_item_id."""
    from bson import ObjectId
    db = get_mongo_db()
    try:
        await db.signals.update_one(
            {"_id": ObjectId(signal_id)},
            {"$set": {"work_item_id": work_item_id}}
        )
    except Exception as e:
        logger.warning("Failed to link signal %s to work item: %s", signal_id, e)


async def invalidate_dashboard_cache(work_item_id: str | None = None) -> None:
    """Invalidate Redis hot-path cache entries."""
    redis = get_redis()
    keys_to_delete = ["ims:dashboard:active"]
    if work_item_id:
        keys_to_delete.append(f"ims:workitem:{work_item_id}")
    if keys_to_delete:
        await redis.delete(*keys_to_delete)
