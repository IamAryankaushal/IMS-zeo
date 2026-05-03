"""RCA submission endpoint with mandatory validation."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connections import get_db_session
from app.models.orm import RCARecord, WorkItem
from app.models.schemas import RCACreateRequest, RCAResponse
from app.services.signal_service import invalidate_dashboard_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rca", tags=["rca"])


@router.post("/{work_item_id}", response_model=RCAResponse, status_code=201)
async def submit_rca(
    work_item_id: UUID,
    body: RCACreateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Submit RCA for a work item.
    - Requires all fields to be non-empty (validated by Pydantic schema).
    - Calculates MTTR automatically.
    - After RCA is submitted, the work item can be transitioned to CLOSED.
    """
    # Verify work item exists
    result = await db.execute(
        select(WorkItem).where(WorkItem.id == work_item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")

    # Check for existing RCA
    existing = await db.execute(
        select(RCARecord).where(RCARecord.work_item_id == work_item_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="RCA already exists for this work item. Delete or update it.",
        )

    # Verify work item is in a suitable state
    if item.status not in ("INVESTIGATING", "RESOLVED"):
        raise HTTPException(
            status_code=422,
            detail=f"RCA can only be submitted for INVESTIGATING or RESOLVED items. "
                   f"Current status: {item.status}",
        )

    rca = RCARecord(
        work_item_id=work_item_id,
        incident_start=body.incident_start,
        incident_end=body.incident_end,
        root_cause_category=body.root_cause_category,
        root_cause_description=body.root_cause_description,
        fix_applied=body.fix_applied,
        prevention_steps=body.prevention_steps,
        submitted_by=body.submitted_by,
    )
    db.add(rca)
    await db.flush()

    # Auto-update MTTR on the work item
    mttr = int((body.incident_end - body.incident_start).total_seconds())
    item.mttr_seconds = mttr

    await invalidate_dashboard_cache(str(work_item_id))
    logger.info(
        "RCA submitted for work item %s | MTTR=%ds | category=%s",
        work_item_id, mttr, body.root_cause_category
    )
    return RCAResponse.model_validate(rca)


@router.get("/{work_item_id}", response_model=RCAResponse)
async def get_rca(
    work_item_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(RCARecord).where(RCARecord.work_item_id == work_item_id)
    )
    rca = result.scalar_one_or_none()
    if not rca:
        raise HTTPException(status_code=404, detail="RCA not found for this work item")
    return RCAResponse.model_validate(rca)
