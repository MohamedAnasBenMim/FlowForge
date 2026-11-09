# FlowForge

FlowForge is a durable workflow execution engine for long-running, multi-step business processes. A REST API accepts workflow definitions and idempotent execution requests, Redis distributes work, and PostgreSQL persists every state transition so an interrupted execution can continue after a worker restart.

## Engineering highlights

- FastAPI REST API with generated OpenAPI documentation
- PostgreSQL/SQLAlchemy persistence for definitions and executions
- Redis-backed worker queue with horizontally scalable workers
- Request idempotency enforced by a database uniqueness constraint
- Exponential retry policy with persisted attempt state
- Heartbeats and stale-execution recovery after worker failure
- Docker Compose environment for the API, workers, PostgreSQL, and Redis
- Pytest integration suite and Locust throughput/p95 benchmark

## Execution model

```text
Client -> REST API -> PostgreSQL transaction -> Redis queue -> Worker
                         ^                                  |
                         +------ persisted transition -----+
```

Each worker executes one step and persists the new context before queuing the next step. If the process dies, the last committed step remains the source of truth. A recovery job can move stale `running` executions back to `queued`.

## Supported steps

The MVP includes deterministic `set`, `increment`, and `copy` operations. The step registry is deliberately small and safe; production integrations can add HTTP, email, event-publish, and domain-specific executors behind the same worker boundary.

## Run locally

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8000/docs` for the interactive API.

Create a workflow:

```bash
curl -X POST http://localhost:8000/v1/workflows \
  -H 'Content-Type: application/json' \
  -d '{"name":"order-flow","steps":[{"name":"mark","operation":"set","key":"status","value":"accepted"}]}'
```

Start it safely (repeating the same key returns the original execution):

```bash
curl -X POST http://localhost:8000/v1/executions \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: order-2026-0001' \
  -d '{"workflow_id":"<workflow-id>","input":{"order_id":"2026-0001"}}'
```

## Tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

The suite verifies successful multi-step execution, duplicate request handling, retry exhaustion, stale worker recovery, and API-level idempotency.

## Performance benchmark

Create a workflow, place its ID in `benchmarks/locustfile.py`, then run:

```bash
locust -f benchmarks/locustfile.py --host http://localhost:8000 \
  --headless -u 100 -r 10 --run-time 60s --csv benchmark
```

Publish requests/second and p50/p95/p99 latency together with CPU, database, Redis, and worker counts so results remain reproducible.

## Production roadmap

- `SELECT ... FOR UPDATE SKIP LOCKED` worker claims for very high concurrency
- Scheduled workflows and cron triggers
- OpenTelemetry traces and Prometheus metrics
- Dead-letter queue management endpoints
- Versioned workflow definitions and compensation steps

## Author

Mohamed Anas Ben Mim — Backend Engineering portfolio project.
