"""Grounded RAG chat/query endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.chat import ChatQueryRequest, ChatQueryResponse
from app.services.generator import GeneratorService

router = APIRouter(prefix="/chat", tags=["Chat"])


def get_generator_service(db: AsyncSession = Depends(get_db)) -> GeneratorService:
    return GeneratorService(db)


@router.post(
    "/query",
    response_model=ChatQueryResponse,
    summary="Ask a question grounded on uploaded documents",
    description=(
        "Runs the full RAG pipeline: query embedding → pgvector retrieval → "
        "CrossEncoder rerank → prompt build → LLM. Answers only from retrieved "
        "context. No conversation memory."
    ),
)
async def chat_query(
    body: ChatQueryRequest,
    service: GeneratorService = Depends(get_generator_service),
) -> ChatQueryResponse:
    payload = await service.answer_question(
        body.question,
        top_k=body.top_k,
        final_k=body.final_k,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    return ChatQueryResponse.model_validate(payload)
