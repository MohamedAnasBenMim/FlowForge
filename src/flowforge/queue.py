from __future__ import annotations

from collections import deque
from typing import Protocol

from redis import Redis

from flowforge.config import get_settings


class ExecutionQueue(Protocol):
    def enqueue(self, execution_id: str) -> None: ...

    def dequeue(self, timeout: int = 5) -> str | None: ...


class RedisExecutionQueue:
    def __init__(self, client: Redis | None = None, name: str | None = None) -> None:
        settings = get_settings()
        self.client = client or Redis.from_url(settings.redis_url, decode_responses=True)
        self.name = name or settings.queue_name

    def enqueue(self, execution_id: str) -> None:
        self.client.lpush(self.name, execution_id)

    def dequeue(self, timeout: int = 5) -> str | None:
        item = self.client.brpop(self.name, timeout=timeout)
        return item[1] if item else None


class MemoryExecutionQueue:
    def __init__(self) -> None:
        self.items: deque[str] = deque()

    def enqueue(self, execution_id: str) -> None:
        self.items.append(execution_id)

    def dequeue(self, timeout: int = 5) -> str | None:
        del timeout
        return self.items.popleft() if self.items else None
