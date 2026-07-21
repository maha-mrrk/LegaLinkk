"""Grounded RAG chat + conversation management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.graphs.rag_graph import build_rag_graph
from app.schemas.chat import ChatQueryRequest, ChatQueryResponse
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
    graph = build_rag_graph(session=db)
    initial_state = {
        "user_question": body.question,
        "metadata": {
            "top_k": body.top_k,
            "final_k": body.final_k,
            "temperature": body.temperature,
            "max_tokens": body.max_tokens,
        },
        "errors": [],
    }
    final_state = await graph.ainvoke(initial_state)

    metadata = final_state.get("metadata") or {}
    payload = {
        "answer": final_state.get("llm_response") or "",
        "sources": metadata.get("sources", []),
        "metadata": metadata.get("generation", {}),
    }
    return ChatQueryResponse.model_validate(payload)
