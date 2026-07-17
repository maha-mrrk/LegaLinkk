"""Document Management API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.document import (
    DocumentChunkListResponse,
    DocumentChunkResponse,
    DocumentIndexResponse,
    DocumentIndexStatusResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
)
from app.services.document import DocumentService
from app.services.document_processing import DocumentProcessingService
from app.services.indexing import IndexingService

router = APIRouter(prefix="/documents", tags=["Documents"])


def get_document_service(db: AsyncSession = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


def get_processing_service(
    db: AsyncSession = Depends(get_db),
) -> DocumentProcessingService:
    return DocumentProcessingService(db)


def get_indexing_service(db: AsyncSession = Depends(get_db)) -> IndexingService:
    return IndexingService(db)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF document",
    description=(
        "Upload a PDF, then automatically run the preprocessing pipeline "
        "(extract → clean → chunk → store)."
    ),
)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to upload"),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    document = await service.upload(file)
    return DocumentResponse.model_validate(document)


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    documents, total = await service.list_documents(skip=skip, limit=limit)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
    )


@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunkListResponse,
    summary="List chunks for a document",
)
async def list_document_chunks(
    document_id: UUID,
    processing: DocumentProcessingService = Depends(get_processing_service),
) -> DocumentChunkListResponse:
    chunks = await processing.get_chunks(document_id)
    return DocumentChunkListResponse(
        document_id=document_id,
        items=[DocumentChunkResponse.from_chunk(chunk) for chunk in chunks],
        total=len(chunks),
    )


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Get document processing status",
)
async def get_document_status(
    document_id: UUID,
    processing: DocumentProcessingService = Depends(get_processing_service),
) -> DocumentStatusResponse:
    document = await processing.get_status(document_id)
    chunks = await processing.get_chunks(document_id)
    return DocumentStatusResponse(
        document_id=document.id,
        status=document.status,
        page_count=document.page_count,
        extraction_method=document.extraction_method,
        chunk_count=len(chunks),
    )


@router.post(
    "/{document_id}/index",
    response_model=DocumentIndexResponse,
    summary="Index document chunks into pgvector",
    description=(
        "Generate multilingual embeddings (bge-m3) for every chunk and upsert "
        "them into PostgreSQL/pgvector. Re-indexing updates existing vectors."
    ),
)
async def index_document(
    document_id: UUID,
    indexing: IndexingService = Depends(get_indexing_service),
) -> DocumentIndexResponse:
    document = await indexing.index_document(document_id)
    return DocumentIndexResponse(
        document_id=document.id,
        index_status=document.index_status,
        indexed_count=document.indexed_chunk_count or 0,
        embedding_model=document.embedding_model,
        indexed_at=document.indexed_at,
        message="Index completed",
    )


@router.get(
    "/{document_id}/index-status",
    response_model=DocumentIndexStatusResponse,
    summary="Get semantic index status",
)
async def get_index_status(
    document_id: UUID,
    indexing: IndexingService = Depends(get_indexing_service),
) -> DocumentIndexStatusResponse:
    payload = await indexing.get_index_status(document_id)
    return DocumentIndexStatusResponse.model_validate(payload)


@router.delete(
    "/{document_id}/index",
    response_model=DocumentIndexResponse,
    summary="Delete semantic index for a document",
)
async def delete_document_index(
    document_id: UUID,
    indexing: IndexingService = Depends(get_indexing_service),
) -> DocumentIndexResponse:
    document = await indexing.delete_index(document_id)
    return DocumentIndexResponse(
        document_id=document.id,
        index_status=document.index_status,
        indexed_count=0,
        embedding_model=None,
        indexed_at=None,
        message="Index deleted",
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get a document by ID",
)
async def get_document(
    document_id: UUID,
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    document = await service.get_document(document_id)
    return DocumentResponse.model_validate(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
async def delete_document(
    document_id: UUID,
    service: DocumentService = Depends(get_document_service),
) -> None:
    await service.delete_document(document_id)
