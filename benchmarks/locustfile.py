from uuid import uuid4

from locust import HttpUser, between, task


class WorkflowUser(HttpUser):
    wait_time = between(0.05, 0.2)
    workflow_id = "set-after-creating-a-workflow"

    @task
    def start_execution(self) -> None:
        self.client.post(
            "/v1/executions",
            headers={"Idempotency-Key": str(uuid4())},
            json={"workflow_id": self.workflow_id, "input": {"events": 0}},
            name="POST /v1/executions",
        )
