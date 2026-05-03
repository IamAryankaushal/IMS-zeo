"""SQLAlchemy ORM models for PostgreSQL."""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.connections import Base


class WorkItem(Base):
    __tablename__ = "work_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    component_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN", index=True
    )
    priority: Mapped[str] = mapped_column(
        String(5), nullable=False, default="P2", index=True
    )
    signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_signal_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_signal_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mttr_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now()
    )

    rca: Mapped["RCARecord | None"] = relationship(
        "RCARecord", back_populates="work_item", uselist=False, lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN','INVESTIGATING','RESOLVED','CLOSED')",
            name="ck_work_items_status"
        ),
        CheckConstraint(
            "priority IN ('P0','P1','P2','P3')",
            name="ck_work_items_priority"
        ),
    )


class RCARecord(Base):
    __tablename__ = "rca_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="CASCADE"),
        nullable=False, unique=True
    )
    incident_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    incident_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    root_cause_category: Mapped[str] = mapped_column(String(50), nullable=False)
    root_cause_description: Mapped[str] = mapped_column(Text, nullable=False)
    fix_applied: Mapped[str] = mapped_column(Text, nullable=False)
    prevention_steps: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_by: Mapped[str] = mapped_column(
        String(100), nullable=False, default="engineer"
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    work_item: Mapped["WorkItem"] = relationship(
        "WorkItem", back_populates="rca"
    )

    __table_args__ = (
        CheckConstraint(
            "root_cause_category IN ("
            "'HARDWARE_FAILURE','SOFTWARE_BUG','CONFIGURATION_ERROR',"
            "'CAPACITY_EXHAUSTION','NETWORK_ISSUE','HUMAN_ERROR',"
            "'THIRD_PARTY_DEPENDENCY','UNKNOWN')",
            name="ck_rca_category"
        ),
    )
