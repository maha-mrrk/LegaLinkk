"""Grounded RAG chat + conversation management endpoints."""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.session import get_db
from app.graphs.rag_graph import build_rag_graph
from app.schemas.chat import (
    ChatDocumentResponse,
    ChatQueryRequest,
    ChatQueryResponse,
)
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationResponse,
    MessageResponse,
)
from app.services.conversation import ConversationService
from app.services.generator import GeneratorService
from app.services.langfuse_service import get_langfuse_service

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


def get_generator_service(db: AsyncSession = Depends(get_db)) -> GeneratorService:
    return GeneratorService(db)


def get_conversation_service(
    db: AsyncSession = Depends(get_db),
) -> ConversationService:
    return ConversationService(db)


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a conversation",
)
async def create_conversation(
    body: ConversationCreateRequest | None = None,
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationResponse:
    title = body.title if body is not None else None
    conversation = await service.create_conversation(title=title)
    return ConversationResponse.from_orm(conversation, include_messages=False)


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List conversations",
)
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationListResponse:
    items, total = await service.list_conversations(skip=skip, limit=limit)
    return ConversationListResponse(
        items=[
            ConversationResponse.from_orm(item, include_messages=False)
            for item in items
        ],
        total=total,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get a conversation with messages",
)
async def get_conversation(
    conversation_id: UUID,
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationResponse:
    conversation = await service.get_conversation(
        conversation_id, with_messages=True
    )
    return ConversationResponse.from_orm(conversation, include_messages=True)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
)
async def delete_conversation(
    conversation_id: UUID,
    service: ConversationService = Depends(get_conversation_service),
) -> None:
    await service.delete_conversation(conversation_id)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessageResponse,
    summary="Send a message in a conversation",
    description=(
        "Stores the user message, loads recent history, runs retrieve→rerank→LLM, "
        "then stores the assistant reply."
    ),
)
async def post_conversation_message(
    conversation_id: UUID,
    body: ConversationMessageRequest,
    conversations: ConversationService = Depends(get_conversation_service),
    generator: GeneratorService = Depends(get_generator_service),
) -> ConversationMessageResponse:
    payload = await conversations.send_user_message(
        conversation_id,
        content=body.content,
        generator=generator,
        top_k=body.top_k,
        final_k=body.final_k,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    return ConversationMessageResponse(
        conversation_id=payload["conversation_id"],
        user_message=MessageResponse.from_orm_message(payload["user_message"]),
        assistant_message=MessageResponse.from_orm_message(
            payload["assistant_message"]
        ),
        answer=payload["answer"],
        sources=payload["sources"],
        metadata=payload["metadata"],
    )


@router.post(
    "/query",
    response_model=ChatQueryResponse,
    summary="Ask a one-shot question (no conversation persistence)",
    description=(
        "Runs the LangGraph RAG pipeline (embedding → retrieval → rerank → "
        "generate) without storing conversation history. Prefer "
        "POST /chat/conversations/{id}/messages for multi-turn chat."
    ),
)
async def chat_query(
    body: ChatQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatQueryResponse:
    # Optional parent trace grouping every RAG node into one run.
    langfuse = get_langfuse_service()
    trace = langfuse.start_trace(
        "rag",
        input={"question": body.question},
        metadata={
            "workflow": "rag",
            "top_k": body.top_k,
            "final_k": body.final_k,
        },
    )
    graph = build_rag_graph(session=db, langfuse=langfuse, trace=trace)
    initial_state = {
        "user_question": body.question,
        # None → search the whole library; a UUID scopes retrieval to one document.
        "document_id": str(body.document_id) if body.document_id else None,
        "metadata": {
            "top_k": body.top_k,
            "final_k": body.final_k,
            "temperature": body.temperature,
            "max_tokens": body.max_tokens,
        },
        "errors": [],
    }
    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as exc:
        langfuse.end_trace(trace, error=exc)
        raise

    metadata = final_state.get("metadata") or {}
    payload = {
        "answer": final_state.get("llm_response") or "",
        "sources": metadata.get("sources", []),
        "metadata": metadata.get("generation", {}),
    }
    langfuse.end_trace(
        trace,
        output={
            "answer": payload["answer"],
            "sources_count": len(payload["sources"] or []),
        },
        metadata=metadata.get("generation", {}),
    )
    return ChatQueryResponse.model_validate(payload)


@router.post(
    "/document",
    response_model=ChatDocumentResponse,
    summary="Generate a grounded document (HTML, printable to PDF)",
    description=(
        "Runs the same grounded retrieve → rerank pipeline as /chat/query but "
        "asks the model to produce a complete, self-contained HTML document "
        "instead of a plain-text answer. The frontend can preview it, print it "
        "to PDF, or download the .html file."
    ),
)
async def chat_document(
    body: ChatQueryRequest,
    generator: GeneratorService = Depends(get_generator_service),
) -> ChatDocumentResponse:
    result = await generator.generate_document(
        body.question,
        top_k=body.top_k,
        final_k=body.final_k,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        document_id=body.document_id,
    )
    return ChatDocumentResponse.model_validate(result)


@router.post(
    "/stream",
    summary="Ask a question with a streamed (fragmented) answer",
    description=(
        "Same grounded retrieve → rerank → generate pipeline as /chat/query, but "
        "streams the answer token-by-token over Server-Sent Events so the UI can "
        "render it progressively instead of waiting for the full response. "
        "Events: 'sources' (once), 'delta' (many), 'done' (once), 'error'."
    ),
)
async def chat_stream(
    body: ChatQueryRequest,
    generator: GeneratorService = Depends(get_generator_service),
) -> StreamingResponse:
    async def event_source():
        try:
            async for event in generator.stream_answer(
                body.question,
                top_k=body.top_k,
                final_k=body.final_k,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
                document_id=body.document_id,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except AppError as exc:
            # Domain errors already carry a professional, user-safe message.
            logger.warning("Chat stream failed: %s", getattr(exc, "detail", exc.message))
            payload = {
                "type": "error",
                "message": exc.message,
                "code": exc.code,
                "retryable": exc.retryable,
            }
            yield f"data: {json.dumps(payload)}\n\n"
        except Exception:  # never leak internals to the client
            logger.exception("Chat stream failed")
            payload = {
                "type": "error",
                "message": (
                    "Une erreur inattendue est survenue pendant la génération "
                    "de la réponse. Veuillez réessayer."
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
            # Disable proxy buffering so fragments flush immediately.
            "X-Accel-Buffering": "no",
        },
    )
