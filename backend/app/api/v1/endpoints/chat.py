"""Grounded RAG chat + conversation management endpoints."""

import asyncio
import json
import re
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.user import User
from app.models.generated_document import GeneratedDocumentKind
from app.graphs.rag_graph import build_rag_graph
from app.schemas.chat import (
    ChatDocumentPdfRequest,
    ChatDocumentResponse,
    ChatJobCreateRequest,
    ChatJobCreateResponse,
    ChatJobStatusResponse,
    ChatQueryRequest,
    ChatQueryResponse,
)
from app.services.pdf import brand_report_html, render_html_to_pdf
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationResponse,
    MessageResponse,
)
from app.services.conversation import ConversationService
from app.services.chat_job import get_chat_job_store
from app.services.generator import GeneratorService
from app.services.generated_document import GeneratedDocumentService
from app.services.langfuse_service import get_langfuse_service
from app.tasks.chat import process_chat_job_task

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
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    title = body.title if body is not None else None
    conversation = await service.create_conversation(
        user_id=current_user.id, title=title
    )
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
    current_user: User = Depends(get_current_user),
) -> ConversationListResponse:
    items, total = await service.list_conversations(
        user_id=current_user.id, skip=skip, limit=limit
    )
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
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    conversation = await service.get_conversation(
        conversation_id,
        user_id=current_user.id,
        with_messages=True,
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
    current_user: User = Depends(get_current_user),
) -> None:
    await service.delete_conversation(
        conversation_id, user_id=current_user.id
    )


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
    current_user: User = Depends(get_current_user),
) -> ConversationMessageResponse:
    payload = await conversations.send_user_message(
        conversation_id,
        user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
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
            "user_id": str(current_user.id),
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
    "/jobs",
    response_model=ChatJobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a reconnectable background chat generation",
)
async def create_chat_job(
    body: ChatJobCreateRequest,
    current_user: User = Depends(get_current_user),
) -> ChatJobCreateResponse:
    """Queue generation independently from the browser's HTTP connection."""
    store = get_chat_job_store()
    job_id = uuid4()
    payload = body.model_dump(mode="json", exclude={"mode"})
    await store.create(
        str(job_id),
        user_id=current_user.id,
        mode=body.mode,
    )
    try:
        result = await asyncio.to_thread(
            process_chat_job_task.delay,
            str(job_id),
            str(current_user.id),
            body.mode,
            payload,
        )
        await store.set_task_id(str(job_id), result.id)
    except Exception as exc:
        logger.exception("Could not queue chat job job_id=%s", job_id)
        await store.mark_failed(
            str(job_id),
            "La réponse n'a pas pu être démarrée. Veuillez réessayer.",
        )
        raise AppError(
            "La réponse n'a pas pu être démarrée. Veuillez réessayer.",
            status_code=503,
            code="chat_job_enqueue_failed",
            retryable=True,
        ) from exc
    return ChatJobCreateResponse(job_id=job_id, status="queued")


@router.get(
    "/jobs/{job_id}",
    response_model=ChatJobStatusResponse,
    summary="Get a background chat job status",
)
async def get_chat_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
) -> ChatJobStatusResponse:
    store = get_chat_job_store()
    meta = await store.get_meta_for_user(str(job_id), user_id=current_user.id)
    _events, event_count = await store.get_events(str(job_id))
    return ChatJobStatusResponse(
        job_id=job_id,
        mode=meta["mode"],
        status=meta["status"],
        event_count=event_count,
    )


@router.get(
    "/jobs/{job_id}/stream",
    summary="Stream or resume a background chat response",
)
async def stream_chat_job(
    job_id: UUID,
    after: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    store = get_chat_job_store()
    await store.get_meta_for_user(str(job_id), user_id=current_user.id)

    async def event_source():
        cursor = after
        while True:
            events, cursor = await store.get_events(str(job_id), after=cursor)
            for event in events:
                yield f"data: {json.dumps(event, default=str)}\n\n"

            meta = await store.get_meta_for_user(
                str(job_id),
                user_id=current_user.id,
            )
            if meta["status"] in {"completed", "failed"} and not events:
                break
            if not events:
                yield ": keepalive\n\n"
                await asyncio.sleep(0.4)

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatDocumentResponse:
    result = await generator.generate_document(
        body.question,
        user_id=current_user.id,
        top_k=body.top_k,
        final_k=body.final_k,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        document_id=body.document_id,
    )
    result["html"] = brand_report_html(result["html"])
    pdf_bytes = await asyncio.to_thread(render_html_to_pdf, result["html"])
    title = f"Rapport — {body.question.strip()[:100]}"
    source_ids = {
        UUID(str(source["document_id"]))
        for source in result.get("sources", [])
        if source.get("document_id")
    }
    source_document_id = body.document_id or (
        next(iter(source_ids)) if len(source_ids) == 1 else None
    )
    generated = await GeneratedDocumentService(db).save_pdf(
        pdf_bytes,
        user_id=current_user.id,
        source_document_id=source_document_id,
        title=title,
        filename=f"{title}.pdf",
        kind=GeneratedDocumentKind.CHAT_REPORT,
        question=body.question,
    )
    return ChatDocumentResponse.model_validate(
        {**result, "generated_document_id": generated.id}
    )


def _safe_pdf_filename(name: str | None) -> str:
    """Return a safe ``*.pdf`` filename (no path traversal / header injection)."""
    base = (name or "").strip() or "document-legallink"
    base = base.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if base.lower().endswith(".pdf"):
        base = base[:-4]
    base = re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip(" .") or "document-legallink"
    return f"{base[:120]}.pdf"


@router.post(
    "/document/pdf",
    summary="Convert a generated HTML document to a downloadable PDF",
    description=(
        "Renders a self-contained HTML document (as produced by /chat/document) "
        "to a print-quality PDF using WeasyPrint. External resource loading is "
        "disabled during rendering. Returns application/pdf as an attachment."
    ),
)
async def chat_document_pdf(
    body: ChatDocumentPdfRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    pdf_bytes = await asyncio.to_thread(render_html_to_pdf, body.html)
    filename = _safe_pdf_filename(body.filename)
    generated = await GeneratedDocumentService(db).save_pdf(
        pdf_bytes,
        user_id=current_user.id,
        source_document_id=body.source_document_id,
        title=body.title,
        filename=filename,
        kind=body.kind,
        question=body.question,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Generated-Document-Id": str(generated.id),
        },
    )


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
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    async def event_source():
        try:
            async for event in generator.stream_answer(
                body.question,
                user_id=current_user.id,
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
