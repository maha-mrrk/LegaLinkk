"""Multi-agent orchestration API endpoints."""

import json
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.legal import LegalAgent
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.session import get_db
from app.graphs.multi_agent_graph import build_multi_agent_graph
from app.schemas.agents import (
    AgentAnswer,
    AgentQueryRequest,
    AgentQueryResponse,
    LegalAnalysisResponse,
    LegalAnalyzeRequest,
)
from app.services.agent_stream import AgentStreamService
from app.services.contract_analysis import ContractAnalysisService
from app.services.conversation import ConversationService
from app.services.generator import GeneratorService
from app.services.langfuse_service import get_langfuse_service
from app.state.graph_state import GraphState

logger = get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["Agents"])


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


def _to_answer(result: dict[str, Any] | None) -> AgentAnswer | None:
    """Adapt a graph agent-result dict to the API schema (``None`` if absent)."""
    if not result:
        return None
    return AgentAnswer.model_validate(result)


@router.post(
    "/query",
    response_model=AgentQueryResponse,
    summary="Route a question through the multi-agent LangGraph",
    description=(
        "Runs the multi-agent StateGraph. A leading '/legal', '/finance' or "
        "'/compliance' command runs only that agent; otherwise the legal, "
        "finance and compliance agents run and a synthesis agent produces a "
        "final recommendation from their three analyses."
    ),
)
async def agents_query(
    body: AgentQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> AgentQueryResponse:
    settings = get_settings()
    langfuse = get_langfuse_service()

    # Parent trace grouping every node of this run into one readable tree.
    trace = langfuse.start_trace("multi_agent", input={"question": body.question})
    graph = build_multi_agent_graph(
        session=db, settings=settings, langfuse=langfuse, trace=trace
    )
    initial: GraphState = {
        "user_query": body.question,
        "metadata": {
            "top_k": body.top_k,
            "final_k": body.final_k,
            "temperature": body.temperature,
            "max_tokens": body.max_tokens,
            "document_id": body.document_id,
        },
        "errors": [],
    }
    try:
        final: GraphState = await graph.ainvoke(initial)
    except Exception as exc:
        langfuse.end_trace(trace, error=exc)
        raise
    langfuse.end_trace(trace, output={"target_agent": final.get("target_agent")})

    target = final.get("target_agent")
    if target:
        result = final.get(f"{target}_result")
        return AgentQueryResponse(
            question=body.question,
            mode="single",
            agent=(result or {}).get("agent"),
            response=_to_answer(result),
        )

    return AgentQueryResponse(
        question=body.question,
        mode="multi",
        recommendation=final.get("final_recommendation"),
        legal=_to_answer(final.get("legal_result")),
        finance=_to_answer(final.get("finance_result")),
        compliance=_to_answer(final.get("compliance_result")),
    )


@router.post(
    "/stream",
    summary="Stream an agent answer (fragmented) over Server-Sent Events",
    description=(
        "Streaming counterpart of POST /agents/query. A leading '/legal', "
        "'/finance' or '/compliance' command streams that single agent's grounded "
        "answer token-by-token. Without a command, the three agents run and the "
        "synthesis recommendation is streamed after their analyses. "
        "Events: 'agent' (once), 'status'/'analyses' (multi mode), 'sources', "
        "'delta' (many), 'done' (once), 'error'."
    ),
)
async def agents_stream(
    body: AgentQueryRequest,
    generator: GeneratorService = Depends(get_generator_service),
) -> StreamingResponse:
    service = AgentStreamService(generator)

    async def event_source():
        try:
            async for event in service.stream(
                body.question,
                document_id=body.document_id,
                top_k=body.top_k,
                final_k=body.final_k,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except AppError as exc:
            logger.warning("Agent stream failed: %s", getattr(exc, "detail", exc.message))
            payload = {
                "type": "error",
                "message": exc.message,
                "code": exc.code,
                "retryable": exc.retryable,
            }
            yield f"data: {json.dumps(payload)}\n\n"
        except Exception:  # never leak internals to the client
            logger.exception("Agent stream failed")
            payload = {
                "type": "error",
                "message": (
                    "Une erreur inattendue est survenue pendant l'interrogation "
                    "des agents. Veuillez réessayer."
                ),
                "code": "internal_error",
                "retryable": True,
            }
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/legal/analyze",
    response_model=LegalAnalysisResponse,
    summary="Analyze a contract with the LegalAgent",
    description=(
        "Runs the specialized LegalAgent over the shared RAG pipeline: explains "
        "clauses, identifies obligations/rights, flags missing or ambiguous "
        "clauses, and returns a structured legal risk assessment. For a scoped "
        "document, an existing analysis is returned unless force_refresh is true."
    ),
)
async def legal_analyze(
    body: LegalAnalyzeRequest,
    legal_agent: LegalAgent = Depends(get_legal_agent),
    conversations: ConversationService = Depends(get_conversation_service),
    db: AsyncSession = Depends(get_db),
) -> LegalAnalysisResponse:
    history = None
    if body.conversation_id is not None:
        messages = await conversations.load_history(body.conversation_id)
        history = ConversationService.messages_to_prompt_turns(messages)

    service = ContractAnalysisService(db, legal_agent)
    payload = await service.get_or_analyze(
        body.question,
        document_id=body.document_id,
        force_refresh=body.force_refresh,
        top_k=body.top_k,
        final_k=body.final_k,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        history=history,
    )
    return LegalAnalysisResponse.model_validate(payload)
