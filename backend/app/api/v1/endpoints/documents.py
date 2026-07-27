"""Document Management API endpoints."""

import re
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.document import (
    DocumentChunkListResponse,
    DocumentChunkResponse,
    DocumentIndexResponse,
    DocumentIndexStatusResponse,
    DocumentListResponse,
    DocumentProgressResponse,
    DocumentReindexResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
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
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a PDF document",
    description=(
        "Upload a PDF and immediately queue the processing pipeline "
        "(extract → OCR → clean → chunk → embed → index) as a background task. "
        "Returns instantly with a task id; poll GET /documents/{id}/progress for "
        "live status."
    ),
)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to upload"),
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> DocumentUploadResponse:
    result = await service.upload(file, user_id=current_user.id)
    return DocumentUploadResponse(
        document_id=result.document.id,
        task_id=result.task_id,
        status=result.document.status,
        filename=result.document.original_filename,
        message=(
            "Upload received. Processing has started."
            if result.task_id
            else "Upload received, but processing could not be queued. Please retry."
        ),
    )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    documents, total = await service.list_documents(
        user_id=current_user.id, skip=skip, limit=limit
    )
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
    current_user: User = Depends(get_current_user),
) -> DocumentChunkListResponse:
    chunks = await processing.get_chunks(
        document_id, user_id=current_user.id
    )
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
    current_user: User = Depends(get_current_user),
) -> DocumentStatusResponse:
    document = await processing.get_status(
        document_id, user_id=current_user.id
    )
    chunks = await processing.get_chunks(
        document_id, user_id=current_user.id
    )
    return DocumentStatusResponse(
        document_id=document.id,
        status=document.status,
        page_count=document.page_count,
        extraction_method=document.extraction_method,
        chunk_count=len(chunks),
    )


@router.get(
    "/{document_id}/progress",
    response_model=DocumentProgressResponse,
    summary="Get live ingestion progress",
    description=(
        "Return the real-time progress of a document's background processing: "
        "current stage, percentage, message, timeline, and any error. Poll this "
        "endpoint while the document is being processed."
    ),
)
async def get_document_progress(
    document_id: UUID,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> DocumentProgressResponse:
    payload = await service.get_progress(
        document_id, user_id=current_user.id
    )
    return DocumentProgressResponse.model_validate(payload)


@router.post(
    "/{document_id}/reprocess",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-run preprocessing for a document",
    description=(
        "Re-queue the background pipeline (extract → clean → chunk → embed → "
        "index) for an existing document. Useful after a failed processing "
        "attempt. Returns immediately; poll GET /documents/{id}/progress."
    ),
)
async def reprocess_document(
    document_id: UUID,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> DocumentUploadResponse:
    result = await service.reprocess(document_id, user_id=current_user.id)
    return DocumentUploadResponse(
        document_id=result.document.id,
        task_id=result.task_id,
        status=result.document.status,
        filename=result.document.original_filename,
        message=(
            "Reprocessing has started."
            if result.task_id
            else "Could not queue reprocessing. Please retry."
        ),
    )


@router.post(
    "/reindex",
    response_model=DocumentReindexResponse,
    summary="Re-index every processed document",
    description=(
        "For each processed document: remove existing embeddings, regenerate "
        "vectors with the embedding model, and store them in PostgreSQL/pgvector."
    ),
)
async def reindex_documents(
    indexing: IndexingService = Depends(get_indexing_service),
    current_user: User = Depends(get_current_user),
) -> DocumentReindexResponse:
    payload = await indexing.reindex_all(user_id=current_user.id)
    return DocumentReindexResponse.model_validate(payload)


@router.post(
    "/{document_id}/index",
    response_model=DocumentIndexResponse,
    summary="Index document chunks into pgvector",
    description=(
        "Generate multilingual embeddings (bge-m3) for every chunk and store "
        "them into PostgreSQL/pgvector. Existing embeddings are replaced."
    ),
)
async def index_document(
    document_id: UUID,
    indexing: IndexingService = Depends(get_indexing_service),
    current_user: User = Depends(get_current_user),
) -> DocumentIndexResponse:
    document = await indexing.index_document(
        document_id, user_id=current_user.id
    )
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
    current_user: User = Depends(get_current_user),
) -> DocumentIndexStatusResponse:
    payload = await indexing.get_index_status(
        document_id, user_id=current_user.id
    )
    return DocumentIndexStatusResponse.model_validate(payload)


@router.delete(
    "/{document_id}/index",
    response_model=DocumentIndexResponse,
    summary="Delete semantic index for a document",
)
async def delete_document_index(
    document_id: UUID,
    indexing: IndexingService = Depends(get_indexing_service),
    current_user: User = Depends(get_current_user),
) -> DocumentIndexResponse:
    document = await indexing.delete_index(
        document_id, user_id=current_user.id
    )
    return DocumentIndexResponse(
        document_id=document.id,
        index_status=document.index_status,
        indexed_count=0,
        embedding_model=None,
        indexed_at=None,
        message="Index deleted",
    )


def _safe_pdf_filename(name: str | None) -> str:
    """Return a safe ``*.pdf`` filename (no path traversal / header injection)."""
    base = (name or "").strip() or "document"
    base = base.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if base.lower().endswith(".pdf"):
        base = base[:-4]
    base = re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip(" .") or "document"
    return f"{base[:120]}.pdf"


@router.get(
    "/{document_id}/file",
    summary="View or download the original PDF file",
    description=(
        "Stream the stored PDF. Served inline by default (for in-browser "
        "preview); pass ?download=true to force a file download."
    ),
)
async def get_document_file(
    document_id: UUID,
    download: bool = Query(False, description="Force an attachment download"),
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    path, original_filename = await service.get_file(
        document_id, user_id=current_user.id
    )
    safe_name = _safe_pdf_filename(original_filename)
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{safe_name}"'},
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get a document by ID",
)
async def get_document(
    document_id: UUID,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    document = await service.get_document(
        document_id, user_id=current_user.id
    )
    return DocumentResponse.model_validate(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
async def delete_document(
    document_id: UUID,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> None:
    await service.delete_document(document_id, user_id=current_user.id)
