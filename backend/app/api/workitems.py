"""Work item CRUD + state transition endpoints."""
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.state_machine import validate_transition
from app.db.connections import get_db_session, get_mongo_db, get_redis
from app.models.orm import WorkItem
from app.models.schemas import (
    TransitionRequest,
    WorkItemListResponse,
    WorkItemResponse,
    RawSignalResponse,
)
from app.services.signal_service import invalidate_dashboard_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workitems", tags=["workitems"])

CACHE_TTL = 30  # seconds


@router.get("", response_model=WorkItemListResponse, summary="List all work items")
async def list_work_items(
    status_filter: str | None = None,
    priority_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
):
    # Try Redis cache for the default "active incidents" query
    redis = get_redis()
    cache_key = "ims:dashboard:active"
    use_cache = (
        status_filter is None and priority_filter is None
        and limit == 50 and offset == 0
    )

    if use_cache:
        cached = await redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            return WorkItemListResponse(**data)

    stmt = select(WorkItem)
    if status_filter:
        stmt = stmt.where(WorkItem.status == status_filter.upper())
    if priority_filter:
        stmt = stmt.where(WorkItem.priority == priority_filter.upper())
    stmt = stmt.order_by(WorkItem.priority.asc(), WorkItem.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)

    count_stmt = select(func.count()).select_from(WorkItem)
    if status_filter:
        count_stmt = count_stmt.where(WorkItem.status == status_filter.upper())
    if priority_filter:
        count_stmt = count_stmt.where(WorkItem.priority == priority_filter.upper())

    result = await db.execute(stmt)
    items = result.scalars().all()
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    response = WorkItemListResponse(
        items=[WorkItemResponse.model_validate(i) for i in items],
        total=total,
    )

    if use_cache:
        await redis.setex(cache_key, CACHE_TTL, response.model_dump_json())

    return response


@router.get("/{work_item_id}", response_model=WorkItemResponse)
async def get_work_item(
    work_item_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    redis = get_redis()
    cache_key = f"ims:workitem:{work_item_id}"
    cached = await redis.get(cache_key)
    if cached:
        return WorkItemResponse(**json.loads(cached))

    result = await db.execute(select(WorkItem).where(WorkItem.id == work_item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")

    response = WorkItemResponse.model_validate(item)
    await redis.setex(cache_key, CACHE_TTL, response.model_dump_json())
    return response


@router.patch("/{work_item_id}/transition", response_model=WorkItemResponse)
async def transition_work_item(
    work_item_id: UUID,
    body: TransitionRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Transition work item status using the state machine."""
    result = await db.execute(select(WorkItem).where(WorkItem.id == work_item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")

    # Validate transition via state machine
    try:
        validate_transition(item.status, body.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Guard: cannot CLOSE without RCA
    if body.status == "CLOSED":
        if not item.rca:
            raise HTTPException(
                status_code=422,
                detail="Cannot close work item without a complete RCA. Submit RCA first.",
            )

    now = datetime.now(timezone.utc)
    item.status = body.status

    if body.status == "RESOLVED":
        item.resolved_at = now
    elif body.status == "CLOSED":
        item.closed_at = now
        # Calculate MTTR
        if item.first_signal_at:
            item.mttr_seconds = int((now - item.first_signal_at).total_seconds())

    await db.flush()
    await invalidate_dashboard_cache(str(work_item_id))
    return WorkItemResponse.model_validate(item)


@router.get("/{work_item_id}/signals", response_model=list[RawSignalResponse])
async def get_work_item_signals(work_item_id: UUID, limit: int = 100):
    """Fetch raw signals from MongoDB for a work item."""
    db = get_mongo_db()
    cursor = db.signals.find(
        {"work_item_id": str(work_item_id)},
        limit=limit,
        sort=[("timestamp", -1)],
    )
    signals = []
    async for doc in cursor:
        signals.append(RawSignalResponse(
            id=str(doc["_id"]),
            component_id=doc.get("component_id", ""),
            component_type=doc.get("component_type", ""),
            error_type=doc.get("error_type", ""),
            message=doc.get("message", ""),
            latency_ms=doc.get("latency_ms"),
            work_item_id=doc.get("work_item_id"),
            timestamp=doc.get("timestamp", datetime.now(timezone.utc)),
            metadata=doc.get("metadata"),
        ))
    return signals
