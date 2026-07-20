"""Semantic retrieval + CrossEncoder reranking API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.retrieval import (
    RerankRequest,
    RerankResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from app.services.reranker import RerankerService
from app.services.retrieval import RetrievalService

router = APIRouter(tags=["Retrieval"])


def get_retrieval_service(db: AsyncSession = Depends(get_db)) -> RetrievalService:
    return RetrievalService(db)


def get_reranker_service(db: AsyncSession = Depends(get_db)) -> RerankerService:
    return RerankerService(db)


@router.post(
    "/retrieve/rerank",
    response_model=RerankResponse,
    summary="Retrieve then CrossEncoder-rerank chunks",
    description=(
        "Retrieve a candidate pool with pgvector cosine search, then rerank with "
        "a multilingual CrossEncoder (bge-reranker-v2-m3). Output is ready for a "
        "future GeneratorService. No LLM generation."
    ),
)
async def retrieve_and_rerank(
    body: RerankRequest,
    service: RerankerService = Depends(get_reranker_service),
) -> RerankResponse:
    payload = await service.retrieve_and_rerank(
        body.query,
        top_k=body.top_k,
        final_k=body.final_k,
    )
    return RerankResponse.model_validate(payload)


@router.post(
    "/retrieve",
    response_model=RetrieveResponse,
    summary="Retrieve Top-K relevant chunks",
    description=(
        "Embed the query and return the most similar indexed chunks from "
        "PostgreSQL/pgvector using cosine similarity. No LLM / RAG generation."
    ),
)
async def retrieve(
    body: RetrieveRequest,
    service: RetrievalService = Depends(get_retrieval_service),
) -> RetrieveResponse:
    payload = await service.retrieve(body.query, top_k=body.top_k)
    return RetrieveResponse.model_validate(payload)
