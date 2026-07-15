"""Document Management API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.document import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


def get_document_service(db: AsyncSession = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF document",
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
