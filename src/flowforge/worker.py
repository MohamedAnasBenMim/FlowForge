import logging

from flowforge.database import SessionLocal
from flowforge.engine import WorkflowEngine
from flowforge.queue import RedisExecutionQueue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("flowforge.worker")


def run() -> None:
    queue = RedisExecutionQueue()
    logger.info("worker started")
    while True:
        execution_id = queue.dequeue()
        if not execution_id:
            continue
        with SessionLocal() as session:
            execution = WorkflowEngine(session, queue).process(execution_id)
            if execution:
                logger.info("execution=%s status=%s", execution.id, execution.status)


if __name__ == "__main__":
    run()
