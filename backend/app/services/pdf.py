"""Render self-contained HTML documents to PDF with WeasyPrint.

Used by the chat "document generation" mode to turn the grounded HTML report the
LLM produces into a downloadable, print-quality PDF (selectable text, real
layout) — without relying on the browser's print dialog.

Security: the generated documents are always self-contained (inline CSS, no
external resources). To prevent SSRF / local-file access during rendering, the
url fetcher rejects everything except inline ``data:`` URIs.
"""

from __future__ import annotations

from app.core.exceptions import AppError, ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)


class PdfRenderError(AppError):
    """Raised when HTML→PDF rendering fails."""

    def __init__(self, message: str = "Failed to render the document to PDF") -> None:
        super().__init__(message, status_code=500, code="pdf_render_error")


def _blocking_url_fetcher(url: str):
    """Allow only inline ``data:`` URIs; block all network/file access."""
    if url.startswith("data:"):
        from weasyprint.urls import default_url_fetcher

        return default_url_fetcher(url)
    raise ValueError(f"Blocked external resource during PDF rendering: {url[:80]}")


def render_html_to_pdf(html: str) -> bytes:
    """Render a self-contained HTML string to PDF bytes.

    Runs the (synchronous, CPU-bound) WeasyPrint pipeline; callers should invoke
    it via ``asyncio.to_thread`` to avoid blocking the event loop.
    """
    if not (html or "").strip():
        raise ValidationError("Cannot render an empty document to PDF")

    try:
        from weasyprint import HTML
    except ImportError as exc:  # pragma: no cover - depends on image build
        logger.exception("WeasyPrint is not installed")
        raise PdfRenderError(
            "Le générateur de PDF n'est pas disponible sur le serveur."
        ) from exc

    try:
        document = HTML(string=html, url_fetcher=_blocking_url_fetcher)
        pdf_bytes = document.write_pdf()
    except Exception as exc:
        logger.exception("HTML→PDF rendering failed")
        raise PdfRenderError() from exc

    logger.info("Rendered document to PDF (%s bytes).", len(pdf_bytes))
    return pdf_bytes
