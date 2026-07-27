"""Pydantic schemas for multi-agent orchestration."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    """Route a question to one or more specialized agents.

    A leading ``/legal`` | ``/finance`` | ``/compliance`` prefix in ``question``
    targets a single agent; otherwise all three run and a synthesis is produced.
    """

    question: str = Field(..., min_length=1, description="User question")
    document_id: UUID | None = Field(
        default=None,
        description="Optional: scope every agent's retrieval to a single contract",
    )
    top_k: int | None = Field(default=None, ge=1, le=50)
    final_k: int | None = Field(default=None, ge=1, le=50)
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, ge=64, le=8192)


class AgentAnswer(BaseModel):
    """One specialized agent's analysis (legal / finance / compliance)."""

    agent: str
    domain: str | None = None
    status: str = "ok"
    answer: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class AgentQueryResponse(BaseModel):
    """Multi-agent graph result.

    Two shapes depending on the leading ``/command``:

    * ``mode="single"`` — a ``/legal`` | ``/finance`` | ``/compliance`` command:
      only ``agent`` + ``response`` are populated.
    * ``mode="multi"`` — no command: ``recommendation`` (the synthesis) plus the
      three individual analyses (``legal`` / ``finance`` / ``compliance``).
    """

    question: str
    mode: Literal["single", "multi"]
    # Single-agent mode.
    agent: str | None = None
    response: AgentAnswer | None = None
    # Default (multi-agent) mode.
    recommendation: str | None = None
    legal: AgentAnswer | None = None
    finance: AgentAnswer | None = None
    compliance: AgentAnswer | None = None


class LegalAnalyzeRequest(BaseModel):
    """Request for a specialized legal contract analysis."""

    question: str = Field(..., min_length=1, description="Legal question")
    conversation_id: UUID | None = Field(
        default=None,
        description="Optional conversation to pull history from (references only)",
    )
    document_id: UUID | None = Field(
        default=None,
        description="Optional: restrict the analysis to a single contract",
    )
    top_k: int | None = Field(default=None, ge=1, le=50)
    final_k: int | None = Field(default=None, ge=1, le=50)
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, ge=64, le=8192)


class LegalAnalysisResponse(BaseModel):
    """Structured legal analysis output."""

    analysis: str
    risk_level: Literal["low", "medium", "high"]
    missing_information: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
