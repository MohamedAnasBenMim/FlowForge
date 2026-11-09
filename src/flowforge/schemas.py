from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class Step(BaseModel):
    name: str
    operation: Literal["set", "increment", "copy"]
    key: str
    value: object | None = None
    source: str | None = None


class WorkflowCreate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=120)]
    steps: Annotated[list[Step], Field(min_length=1, max_length=100)]


class WorkflowRead(BaseModel):
    id: str
    name: str
    steps: list[Step]
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutionCreate(BaseModel):
    workflow_id: str
    input: dict[str, object] = Field(default_factory=dict)


class ExecutionRead(BaseModel):
    id: str
    workflow_id: str
    idempotency_key: str
    status: str
    current_step: int
    attempts: int
    input: dict[str, object]
    context: dict[str, object]
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
