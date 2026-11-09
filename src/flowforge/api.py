from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from flowforge.database import Base, engine, get_session
from flowforge.engine import WorkflowEngine, WorkflowNotFoundError
from flowforge.models import WorkflowExecution
from flowforge.queue import RedisExecutionQueue
from flowforge.schemas import ExecutionCreate, ExecutionRead, WorkflowCreate, WorkflowRead

app = FastAPI(
    title="FlowForge API",
    version="0.1.0",
    description="Durable workflow execution with retries and idempotency.",
)


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(engine)


def get_queue() -> RedisExecutionQueue:
    return RedisExecutionQueue()


SessionDep = Annotated[Session, Depends(get_session)]
QueueDep = Annotated[RedisExecutionQueue, Depends(get_queue)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/workflows", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: WorkflowCreate, session: SessionDep, queue: QueueDep):
    return WorkflowEngine(session, queue).create_workflow(payload)


@app.post("/v1/executions", response_model=ExecutionRead)
def start_execution(
    payload: ExecutionCreate,
    response: Response,
    session: SessionDep,
    queue: QueueDep,
    idempotency_key: Annotated[str, Header(min_length=8, max_length=180)],
):
    try:
        execution, created = WorkflowEngine(session, queue).start_execution(
            payload, idempotency_key
        )
    except WorkflowNotFoundError as error:
        raise HTTPException(status_code=404, detail="Workflow not found") from error
    response.status_code = status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK
    return execution


@app.get("/v1/executions/{execution_id}", response_model=ExecutionRead)
def get_execution(execution_id: str, session: SessionDep):
    execution = session.get(WorkflowExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution
