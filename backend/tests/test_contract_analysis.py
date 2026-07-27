"""Unit tests for persisted get-or-compute contract analyses."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import AppError
from app.models.analysis import ANALYSIS_VERSION, AnalysisStatus, DocumentAnalysis
from app.services.contract_analysis import ContractAnalysisService


def _service() -> tuple[ContractAnalysisService, AsyncMock, AsyncMock]:
    session = AsyncMock()
    legal_agent = AsyncMock()
    service = ContractAnalysisService(session, legal_agent)
    service._documents = AsyncMock()
    service._analyses = AsyncMock()
    return service, session, legal_agent


async def test_completed_matching_analysis_is_returned_without_llm() -> None:
    service, _session, legal_agent = _service()
    document_id = uuid4()
    question = "Analyse ce contrat."
    fingerprint = service._fingerprint(
        question=question,
        top_k=15,
        final_k=5,
        temperature=None,
        max_tokens=None,
    )
    row = DocumentAnalysis(
        document_id=document_id,
        status=AnalysisStatus.COMPLETED,
        payload={
            "analysis": "Analyse enregistrée",
            "risk_level": "low",
            "missing_information": [],
            "sources": [],
            "recommendations": [],
            "metadata": {},
        },
        analysis_version=ANALYSIS_VERSION,
        request_fingerprint=fingerprint,
    )
    row.updated_at = datetime.now(timezone.utc)
    service._documents.get_by_id.return_value = SimpleNamespace(id=document_id)
    service._analyses.get_by_document_id.return_value = row

    result = await service.get_or_analyze(
        question,
        document_id=document_id,
        top_k=15,
        final_k=5,
    )

    assert result["analysis"] == "Analyse enregistrée"
    assert result["metadata"]["cached"] is True
    legal_agent.analyze.assert_not_awaited()


async def test_cache_miss_computes_and_persists_analysis() -> None:
    service, session, legal_agent = _service()
    document_id = uuid4()
    service._documents.get_by_id.return_value = SimpleNamespace(id=document_id)
    service._analyses.get_by_document_id.return_value = None
    legal_agent.analyze.return_value = {
        "analysis": "Nouvelle analyse",
        "risk_level": "medium",
        "missing_information": [],
        "sources": [],
        "recommendations": ["Vérifier la résiliation"],
        "metadata": {"model": "test-model", "risk_findings": []},
    }

    result = await service.get_or_analyze(
        "Analyse ce contrat.",
        document_id=document_id,
        top_k=15,
        final_k=5,
    )

    created = service._analyses.create.await_args.args[0]
    assert created.status == AnalysisStatus.COMPLETED
    assert created.payload["analysis"] == "Nouvelle analyse"
    assert created.model == "test-model"
    assert result["metadata"]["cached"] is False
    assert session.commit.await_count == 2


async def test_processing_analysis_prevents_duplicate_generation() -> None:
    service, _session, legal_agent = _service()
    document_id = uuid4()
    service._documents.get_by_id.return_value = SimpleNamespace(id=document_id)
    service._analyses.get_by_document_id.return_value = DocumentAnalysis(
        document_id=document_id,
        status=AnalysisStatus.PROCESSING,
        analysis_version=ANALYSIS_VERSION,
        request_fingerprint="x" * 64,
    )

    with pytest.raises(AppError) as captured:
        await service.get_or_analyze(
            "Analyse ce contrat.",
            document_id=document_id,
        )

    assert captured.value.status_code == 409
    assert captured.value.code == "analysis_in_progress"
    legal_agent.analyze.assert_not_awaited()


async def test_processing_row_from_previous_process_is_reclaimed() -> None:
    service, session, legal_agent = _service()
    document_id = uuid4()
    row = DocumentAnalysis(
        document_id=document_id,
        status=AnalysisStatus.PROCESSING,
        analysis_version=ANALYSIS_VERSION,
        request_fingerprint="x" * 64,
    )
    row.updated_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    service._documents.get_by_id.return_value = SimpleNamespace(id=document_id)
    service._analyses.get_by_document_id.return_value = row
    legal_agent.analyze.return_value = {
        "analysis": "Analyse récupérée",
        "risk_level": "low",
        "missing_information": [],
        "sources": [],
        "recommendations": [],
        "metadata": {},
    }

    result = await service.get_or_analyze(
        "Analyse ce contrat.",
        document_id=document_id,
    )

    assert result["analysis"] == "Analyse récupérée"
    assert row.status == AnalysisStatus.COMPLETED
    assert session.commit.await_count == 2
