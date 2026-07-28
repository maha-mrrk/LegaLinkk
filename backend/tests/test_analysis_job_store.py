"""Owner isolation and result restoration for durable analysis jobs."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.services.analysis_job import AnalysisJobStore


class FakeRedis:
    def __init__(self, payload: dict[str, str]) -> None:
        self.payload = payload

    def hgetall(self, _key: str) -> dict[str, str]:
        return self.payload


@pytest.mark.asyncio
async def test_completed_analysis_result_is_restored_for_owner() -> None:
    owner_id = uuid4()
    result = {
        "analysis": "Synthèse",
        "risk_level": "medium",
        "risk_score": 60,
    }
    store = AnalysisJobStore(
        FakeRedis(
            {
                "user_id": str(owner_id),
                "document_id": str(uuid4()),
                "status": "completed",
                "progress": "100",
                "message": "Analyse terminée.",
                "result": json.dumps(result),
                "error": "",
            }
        )
    )

    payload = await store.get_for_user("job-1", user_id=owner_id)

    assert payload["status"] == "completed"
    assert payload["progress"] == 100
    assert payload["result"] == result


@pytest.mark.asyncio
async def test_foreign_user_cannot_resume_analysis_job() -> None:
    store = AnalysisJobStore(
        FakeRedis(
            {
                "user_id": str(uuid4()),
                "status": "processing",
                "progress": "20",
            }
        )
    )

    with pytest.raises(NotFoundError):
        await store.get_for_user("job-1", user_id=uuid4())
