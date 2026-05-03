"""Pydantic v2 schemas for API validation and serialisation."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ── Signal Ingestion ─────────────────────────────────────────────────────────

class SignalPayload(BaseModel):
    component_id: str = Field(..., min_length=1, max_length=100, examples=["CACHE_CLUSTER_01"])
    component_type: str = Field(..., examples=["CACHE", "RDBMS", "QUEUE", "API", "MCP"])
    error_type: str = Field(..., examples=["CONNECTION_TIMEOUT", "OOM", "DEADLOCK"])
    message: str = Field(..., max_length=2000)
    latency_ms: float | None = Field(None, ge=0)
    metadata: dict | None = None
    timestamp: datetime | None = None


class SignalIngestResponse(BaseModel):
    accepted: bool
    signal_id: str | None = None
    work_item_id: str | None = None
    rate_limited: bool = False
    queue_size: int = 0


# ── Work Items ───────────────────────────────────────────────────────────────

class WorkItemResponse(BaseModel):
    id: UUID
    component_id: str
    title: str
    status: str
    priority: str
    signal_count: int
    first_signal_at: datetime
    last_signal_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None
    mttr_seconds: int | None
    created_at: datetime
    updated_at: datetime
    rca: "RCAResponse | None" = None

    model_config = {"from_attributes": True}


class WorkItemListResponse(BaseModel):
    items: list[WorkItemResponse]
    total: int


class TransitionRequest(BaseModel):
    status: Literal["OPEN", "INVESTIGATING", "RESOLVED", "CLOSED"]


# ── RCA ──────────────────────────────────────────────────────────────────────

RootCauseCategory = Literal[
    "HARDWARE_FAILURE", "SOFTWARE_BUG", "CONFIGURATION_ERROR",
    "CAPACITY_EXHAUSTION", "NETWORK_ISSUE", "HUMAN_ERROR",
    "THIRD_PARTY_DEPENDENCY", "UNKNOWN"
]


class RCACreateRequest(BaseModel):
    incident_start: datetime
    incident_end: datetime
    root_cause_category: RootCauseCategory
    root_cause_description: str = Field(..., min_length=10, max_length=5000)
    fix_applied: str = Field(..., min_length=10, max_length=5000)
    prevention_steps: str = Field(..., min_length=10, max_length=5000)
    submitted_by: str = Field(default="engineer", max_length=100)

    @field_validator("incident_end")
    @classmethod
    def end_after_start(cls, v, info):
        if "incident_start" in info.data and v <= info.data["incident_start"]:
            raise ValueError("incident_end must be after incident_start")
        return v


class RCAResponse(BaseModel):
    id: UUID
    work_item_id: UUID
    incident_start: datetime
    incident_end: datetime
    root_cause_category: str
    root_cause_description: str
    fix_applied: str
    prevention_steps: str
    submitted_by: str
    submitted_at: datetime

    model_config = {"from_attributes": True}


# ── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    environment: str
    queue_size: int
    queue_capacity: int
    services: dict[str, str]


# ── Signals from MongoDB ──────────────────────────────────────────────────────

class RawSignalResponse(BaseModel):
    id: str
    component_id: str
    component_type: str
    error_type: str
    message: str
    latency_ms: float | None
    work_item_id: str | None
    timestamp: datetime
    metadata: dict | None


WorkItemResponse.model_rebuild()
