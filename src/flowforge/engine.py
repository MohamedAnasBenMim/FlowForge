from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from flowforge.config import Settings, get_settings
from flowforge.models import WorkflowDefinition, WorkflowExecution, now
from flowforge.queue import ExecutionQueue
from flowforge.schemas import ExecutionCreate, Step, WorkflowCreate


class WorkflowNotFoundError(LookupError):
    pass


class WorkflowEngine:
    def __init__(
        self,
        session: Session,
        queue: ExecutionQueue,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.queue = queue
        self.settings = settings or get_settings()

    def create_workflow(self, payload: WorkflowCreate) -> WorkflowDefinition:
        workflow = WorkflowDefinition(
            name=payload.name,
            steps=[step.model_dump(mode="json") for step in payload.steps],
        )
        self.session.add(workflow)
        self.session.commit()
        self.session.refresh(workflow)
        return workflow

    def start_execution(
        self, payload: ExecutionCreate, idempotency_key: str
    ) -> tuple[WorkflowExecution, bool]:
        existing = self.session.scalar(
            select(WorkflowExecution).where(WorkflowExecution.idempotency_key == idempotency_key)
        )
        if existing:
            return existing, False
        if not self.session.get(WorkflowDefinition, payload.workflow_id):
            raise WorkflowNotFoundError(payload.workflow_id)
        execution = WorkflowExecution(
            workflow_id=payload.workflow_id,
            idempotency_key=idempotency_key,
            input=payload.input,
            context=dict(payload.input),
        )
        self.session.add(execution)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.session.scalar(
                select(WorkflowExecution).where(
                    WorkflowExecution.idempotency_key == idempotency_key
                )
            )
            if not existing:
                raise
            return existing, False
        self.session.refresh(execution)
        self.queue.enqueue(execution.id)
        return execution, True

    def process(self, execution_id: str) -> WorkflowExecution | None:
        execution = self.session.get(WorkflowExecution, execution_id)
        if not execution or execution.status in {"completed", "failed"}:
            return execution
        if execution.available_at > now():
            self.queue.enqueue(execution.id)
            return execution
        execution.status = "running"
        execution.heartbeat_at = now()
        workflow = execution.workflow
        try:
            step = Step.model_validate(workflow.steps[execution.current_step])
            execution.context = self._run_step(step, dict(execution.context))
            execution.current_step += 1
            execution.attempts = 0
            execution.last_error = None
            if execution.current_step >= len(workflow.steps):
                execution.status = "completed"
            else:
                execution.status = "queued"
                self.queue.enqueue(execution.id)
        except Exception as error:  # worker boundary: every task failure is persisted
            execution.attempts += 1
            execution.last_error = str(error)
            if execution.attempts >= self.settings.max_attempts:
                execution.status = "failed"
            else:
                delay = self.settings.retry_base_seconds * (2 ** (execution.attempts - 1))
                execution.available_at = now() + timedelta(seconds=delay)
                execution.status = "retrying"
                self.queue.enqueue(execution.id)
        self.session.commit()
        self.session.refresh(execution)
        return execution

    def recover_stale(self, older_than_seconds: int = 60) -> int:
        threshold = now() - timedelta(seconds=older_than_seconds)
        stale = self.session.scalars(
            select(WorkflowExecution).where(
                WorkflowExecution.status == "running",
                WorkflowExecution.heartbeat_at < threshold,
            )
        ).all()
        for execution in stale:
            execution.status = "queued"
            self.queue.enqueue(execution.id)
        self.session.commit()
        return len(stale)

    @staticmethod
    def _run_step(step: Step, context: dict[str, object]) -> dict[str, object]:
        if step.operation == "set":
            context[step.key] = step.value
        elif step.operation == "increment":
            current = context.get(step.key, 0)
            if not isinstance(current, (int, float)) or not isinstance(step.value, (int, float)):
                raise ValueError("increment requires numeric current and step values")
            context[step.key] = current + step.value
        elif step.operation == "copy":
            if not step.source or step.source not in context:
                raise ValueError(f"source key '{step.source}' does not exist")
            context[step.key] = context[step.source]
        return context
