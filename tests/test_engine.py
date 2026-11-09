from datetime import timedelta

from flowforge.config import Settings
from flowforge.engine import WorkflowEngine
from flowforge.models import now
from flowforge.schemas import ExecutionCreate, WorkflowCreate


def workflow_payload() -> WorkflowCreate:
    return WorkflowCreate.model_validate(
        {
            "name": "invoice-processing",
            "steps": [
                {"name": "mark", "operation": "set", "key": "status", "value": "paid"},
                {"name": "count", "operation": "increment", "key": "events", "value": 1},
                {"name": "copy", "operation": "copy", "key": "result", "source": "status"},
            ],
        }
    )


def test_executes_durable_workflow_to_completion(session, queue) -> None:
    engine = WorkflowEngine(session, queue)
    workflow = engine.create_workflow(workflow_payload())
    execution, created = engine.start_execution(
        ExecutionCreate(workflow_id=workflow.id, input={"events": 2}), "invoice-0001"
    )

    assert created is True
    while (execution_id := queue.dequeue()) is not None:
        execution = engine.process(execution_id)

    assert execution.status == "completed"
    assert execution.context == {"events": 3, "status": "paid", "result": "paid"}


def test_idempotency_returns_original_execution(session, queue) -> None:
    engine = WorkflowEngine(session, queue)
    workflow = engine.create_workflow(workflow_payload())
    payload = ExecutionCreate(workflow_id=workflow.id)

    first, first_created = engine.start_execution(payload, "same-business-request")
    second, second_created = engine.start_execution(payload, "same-business-request")

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert len(queue.items) == 1


def test_retries_then_fails_invalid_step(session, queue) -> None:
    settings = Settings(max_attempts=2, retry_base_seconds=0)
    engine = WorkflowEngine(session, queue, settings)
    workflow = engine.create_workflow(
        WorkflowCreate.model_validate(
            {
                "name": "broken",
                "steps": [{"name": "bad", "operation": "increment", "key": "value", "value": 1}],
            }
        )
    )
    execution, _ = engine.start_execution(
        ExecutionCreate(workflow_id=workflow.id, input={"value": "not-a-number"}), "broken-01"
    )

    engine.process(queue.dequeue())
    result = engine.process(queue.dequeue())

    assert result.status == "failed"
    assert result.attempts == 2
    assert "numeric" in result.last_error


def test_recovers_stale_worker_claim(session, queue) -> None:
    engine = WorkflowEngine(session, queue)
    workflow = engine.create_workflow(workflow_payload())
    execution, _ = engine.start_execution(ExecutionCreate(workflow_id=workflow.id), "recovery-01")
    queue.dequeue()
    execution.status = "running"
    execution.heartbeat_at = now() - timedelta(minutes=5)
    session.commit()

    assert engine.recover_stale(older_than_seconds=60) == 1
    assert queue.dequeue() == execution.id
