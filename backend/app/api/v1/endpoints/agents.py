"""Multi-agent orchestration API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.legal import LegalAgent
from app.agents.orchestrator import AgentOrchestrator
from app.db.session import get_db
from app.schemas.agents import (
    AgentQueryRequest,
    AgentQueryResponse,
    LegalAnalysisResponse,
    LegalAnalyzeRequest,
)
from app.services.conversation import ConversationService
from app.services.generator import GeneratorService

router = APIRouter(prefix="/agents", tags=["Agents"])


def get_agent_orchestrator(db: AsyncSession = Depends(get_db)) -> AgentOrchestrator:
    return AgentOrchestrator(db)


def get_generator_service(db: AsyncSession = Depends(get_db)) -> GeneratorService:
    return GeneratorService(db)


def get_conversation_service(
    db: AsyncSession = Depends(get_db),
) -> ConversationService:
    return ConversationService(db)


def get_legal_agent(
    generator: GeneratorService = Depends(get_generator_service),
) -> LegalAgent:
    return LegalAgent(generator)


@router.post(
    "/query",
    response_model=AgentQueryResponse,
    summary="Route a question to specialized AI agents",
    description=(
        "Detects intent (legal / finance / compliance), runs the matching "
        "agents with the shared RAG GeneratorService, and aggregates their "
        "outputs."
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


@router.post(
    "/legal/analyze",
    response_model=LegalAnalysisResponse,
    summary="Analyze a contract with the LegalAgent",
    description=(
        "Runs the specialized LegalAgent over the shared RAG pipeline: explains "
        "clauses, identifies obligations/rights, flags missing or ambiguous "
        "clauses, and returns a rule-based legal risk assessment."
    ),
)
async def legal_analyze(
    body: LegalAnalyzeRequest,
    legal_agent: LegalAgent = Depends(get_legal_agent),
    conversations: ConversationService = Depends(get_conversation_service),
) -> LegalAnalysisResponse:
    history = None
    if body.conversation_id is not None:
        messages = await conversations.load_history(body.conversation_id)
        history = ConversationService.messages_to_prompt_turns(messages)

    payload = await legal_agent.analyze(
        body.question,
        top_k=body.top_k,
        final_k=body.final_k,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        history=history,
        document_id=body.document_id,
    )
    return LegalAnalysisResponse.model_validate(payload)
