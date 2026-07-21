"""Multi-agent orchestration API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import AgentOrchestrator
from app.db.session import get_db
from app.schemas.agents import AgentQueryRequest, AgentQueryResponse

router = APIRouter(prefix="/agents", tags=["Agents"])


def get_agent_orchestrator(db: AsyncSession = Depends(get_db)) -> AgentOrchestrator:
    return AgentOrchestrator(db)


@router.post(
    "/query",
    response_model=AgentQueryResponse,
    summary="Route a question to specialized AI agents",
    description=(
        "Detects intent (legal / finance / compliance), runs the matching "
        "placeholder agents with the shared RAG GeneratorService, and aggregates "
        "their outputs. Domain business logic is not implemented yet."
    ),
)
async def agents_query(
    body: AgentQueryRequest,
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
) -> AgentQueryResponse:
    payload = await orchestrator.query(
        body.question,
        top_k=body.top_k,
        final_k=body.final_k,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    return AgentQueryResponse.model_validate(payload)
