"""Pydantic schemas for multi-agent orchestration."""

from typing import Any

from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    """Route a question to one or more specialized agents."""

    question: str = Field(..., min_length=1, description="User question")
    top_k: int | None = Field(default=None, ge=1, le=50)
    final_k: int | None = Field(default=None, ge=1, le=50)
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, ge=64, le=8192)


class AgentResponseItem(BaseModel):
    agent: str
    status: str
    message: str
    answer: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentQueryResponse(BaseModel):
    question: str
    selected_agents: list[str]
    intent: dict[str, Any] = Field(default_factory=dict)
    responses: list[AgentResponseItem]
    message: str | None = None
