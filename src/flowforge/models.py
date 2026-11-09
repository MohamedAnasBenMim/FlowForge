from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flowforge.database import Base


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    """Return a UTC timestamp without tzinfo for SQLite/PostgreSQL portability."""
    return datetime.now(UTC).replace(tzinfo=None)


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    steps: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    executions: Mapped[list[WorkflowExecution]] = relationship(back_populates="workflow")


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_execution_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_definitions.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    input: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    context: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    workflow: Mapped[WorkflowDefinition] = relationship(back_populates="executions")
