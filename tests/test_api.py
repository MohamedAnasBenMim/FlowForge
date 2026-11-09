from fastapi.testclient import TestClient

from flowforge.api import app, get_queue
from flowforge.database import get_session


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_starts_idempotent_execution(session, queue) -> None:
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_queue] = lambda: queue
    client = TestClient(app)

    workflow = client.post(
        "/v1/workflows",
        json={
            "name": "api-flow",
            "steps": [{"name": "set", "operation": "set", "key": "ok", "value": True}],
        },
    )
    payload = {"workflow_id": workflow.json()["id"], "input": {}}
    first = client.post(
        "/v1/executions", json=payload, headers={"Idempotency-Key": "api-request-001"}
    )
    second = client.post(
        "/v1/executions", json=payload, headers={"Idempotency-Key": "api-request-001"}
    )

    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    app.dependency_overrides.clear()
