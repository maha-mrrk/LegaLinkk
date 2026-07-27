"""Get-or-compute persistence for structured legal contract analyses."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.legal import LegalAgent
from app.core.exceptions import AppError, NotFoundError
from app.core.logging import get_logger
from app.models.analysis import (
    ANALYSIS_VERSION,
    AnalysisStatus,
    DocumentAnalysis,
)
from app.repositories.analysis import DocumentAnalysisRepository
from app.repositories.document import DocumentRepository

logger = get_logger(__name__)

# A PROCESSING row older than this API process was interrupted by a restart.
# Such a row is safe to reclaim; rows started by this process still protect
# against duplicate clicks while their generation is running.
_PROCESS_STARTED_AT = datetime.now(timezone.utc)


class ContractAnalysisService:
    """Return a stored analysis or compute and persist a new one."""

    def __init__(self, session: AsyncSession, legal_agent: LegalAgent) -> None:
        self._session = session
        self._legal_agent = legal_agent
        self._analyses = DocumentAnalysisRepository(session)
        self._documents = DocumentRepository(session)

    async def get_or_analyze(
        self,
        question: str,
        *,
        document_id: UUID | None,
        force_refresh: bool = False,
        top_k: int | None = None,
        final_k: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        history: Sequence[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Reuse a valid stored result, otherwise calculate and save it.

        Unscoped requests are intentionally not cached because their result
        depends on the entire, changing document library.
        """
        if document_id is None:
            return await self._compute(
                question,
                document_id=None,
                top_k=top_k,
                final_k=final_k,
                temperature=temperature,
                max_tokens=max_tokens,
                history=history,
            )

        if await self._documents.get_by_id(document_id) is None:
            raise NotFoundError("Ce contrat est introuvable.")

        fingerprint = self._fingerprint(
            question=question,
            top_k=top_k,
            final_k=final_k,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        row = await self._analyses.get_by_document_id(document_id)

        if (
            not force_refresh
            and row is not None
            and row.status == AnalysisStatus.COMPLETED
            and row.analysis_version == ANALYSIS_VERSION
            and row.request_fingerprint == fingerprint
            and row.payload
        ):
            logger.info(
                "Stored contract analysis returned document_id=%s version=%s",
                document_id,
                ANALYSIS_VERSION,
            )
            return self._response_from_row(row, cached=True)

        if row is not None and row.status == AnalysisStatus.PROCESSING:
            if row.updated_at is None or row.updated_at >= _PROCESS_STARTED_AT:
                raise AppError(
                    "L’analyse de ce contrat est déjà en cours. Veuillez patienter.",
                    status_code=409,
                    code="analysis_in_progress",
                    retryable=True,
                )
            logger.warning(
                "Reclaiming interrupted analysis document_id=%s updated_at=%s",
                document_id,
                row.updated_at,
            )

        created = row is None
        if created:
            row = DocumentAnalysis(
                document_id=document_id,
                status=AnalysisStatus.PROCESSING,
                analysis_version=ANALYSIS_VERSION,
                request_fingerprint=fingerprint,
            )
            await self._analyses.create(row)
        else:
            row.status = AnalysisStatus.PROCESSING
            row.analysis_version = ANALYSIS_VERSION
            row.request_fingerprint = fingerprint
            row.error_message = None
        try:
            await self._session.commit()
        except IntegrityError as exc:
            # A concurrent first request inserted the unique document row after
            # our cache lookup. It owns the generation; never start a duplicate.
            await self._session.rollback()
            logger.info(
                "Concurrent contract analysis already started document_id=%s",
                document_id,
            )
            raise AppError(
                "L’analyse de ce contrat est déjà en cours. Veuillez patienter.",
                status_code=409,
                code="analysis_in_progress",
                retryable=True,
            ) from exc

        try:
            payload = await self._compute(
                question,
                document_id=document_id,
                top_k=top_k,
                final_k=final_k,
                temperature=temperature,
                max_tokens=max_tokens,
                history=history,
            )
        except Exception as exc:
            logger.exception(
                "Contract analysis failed document_id=%s", document_id
            )
            row.status = AnalysisStatus.FAILED
            row.error_message = (
                exc.message
                if isinstance(exc, AppError)
                else "L’analyse du contrat a échoué."
            )
            await self._session.commit()
            raise

        # JSONB receives only JSON-safe values. Current agent payloads already
        # satisfy this; default=str protects UUID/datetime provider metadata.
        stored_payload = json.loads(json.dumps(payload, default=str))
        row.payload = stored_payload
        row.status = AnalysisStatus.COMPLETED
        row.model = str((stored_payload.get("metadata") or {}).get("model") or "") or None
        row.error_message = None
        await self._session.commit()
        await self._session.refresh(row)

        logger.info("Contract analysis stored document_id=%s", document_id)
        return self._response_from_row(row, cached=False)

    async def _compute(
        self,
        question: str,
        *,
        document_id: UUID | None,
        top_k: int | None,
        final_k: int | None,
        temperature: float | None,
        max_tokens: int | None,
        history: Sequence[dict[str, str]] | None,
    ) -> dict[str, Any]:
        return await self._legal_agent.analyze(
            question,
            top_k=top_k,
            final_k=final_k,
            temperature=temperature,
            max_tokens=max_tokens,
            history=history,
            document_id=document_id,
        )

    @staticmethod
    def _fingerprint(
        *,
        question: str,
        top_k: int | None,
        final_k: int | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        parameters = {
            "question": question.strip(),
            "top_k": top_k,
            "final_k": final_k,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "analysis_version": ANALYSIS_VERSION,
        }
        encoded = json.dumps(
            parameters, sort_keys=True, ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _response_from_row(
        row: DocumentAnalysis, *, cached: bool
    ) -> dict[str, Any]:
        payload = dict(row.payload or {})
        metadata = dict(payload.get("metadata") or {})
        metadata.update(
            {
                "cached": cached,
                "analysis_version": row.analysis_version,
                "analyzed_at": (
                    row.updated_at.isoformat() if row.updated_at else None
                ),
            }
        )
        payload["metadata"] = metadata
        return payload


__all__ = ["ContractAnalysisService"]
