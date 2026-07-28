"""Tests for owner-scoped replay of Redis-backed chat events."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.services.chat_job import ChatJobStore


class FakeRedis:
    def __init__(self, meta: dict[str, str], events: list[dict]) -> None:
        self.meta = meta
        self.events = [json.dumps(event) for event in events]

    def hgetall(self, _key: str) -> dict[str, str]:
        return self.meta

    def lrange(self, _key: str, start: int, _end: int) -> list[str]:
        return self.events[start:]


@pytest.mark.asyncio
async def test_replays_events_from_requested_offset_for_owner() -> None:
    owner_id = uuid4()
    client = FakeRedis(
        {"user_id": str(owner_id), "status": "completed", "mode": "chat"},
        [
            {"type": "delta", "text": "A"},
            {"type": "delta", "text": "B"},
            {"type": "done", "answer": "AB"},
        ],
    )
    store = ChatJobStore(client)

    meta = await store.get_meta_for_user("job-1", user_id=owner_id)
    events, cursor = await store.get_events("job-1", after=1)

    assert meta["status"] == "completed"
    assert events == [
        {"type": "delta", "text": "B"},
        {"type": "done", "answer": "AB"},
    ]
    assert cursor == 3


@pytest.mark.asyncio
async def test_foreign_user_cannot_read_chat_job() -> None:
    client = FakeRedis(
        {"user_id": str(uuid4()), "status": "processing", "mode": "agent"},
        [],
    )
    store = ChatJobStore(client)

    with pytest.raises(NotFoundError):
        await store.get_meta_for_user("job-1", user_id=uuid4())
