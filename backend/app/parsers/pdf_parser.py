"""PyMuPDF-based text extraction for digitally generated PDFs."""

from __future__ import annotations

from pathlib import Path

import fitz

from app.core.logging import get_logger
from app.parsers import DocumentParser, PageText, PdfParseError, TextExtractionResult

logger = get_logger(__name__)


class PdfParser(DocumentParser):
    """Extract text from digital PDFs using PyMuPDF (``fitz``).

    Scanned / image-only PDFs typically yield empty text; the extraction
    pipeline falls back to OCR in that case.
    """

    def extract_text(self, file_path: str) -> str:
        """Open the PDF and return all page text as one string."""
        return self.extract(file_path).text

    def extract(self, file_path: str) -> TextExtractionResult:
        """Extract text page-by-page, preserving order, plus page count."""
        path = Path(file_path)
        if not path.is_file():
            message = f"PDF file not found: {file_path}"
            logger.error(message)
            raise PdfParseError(message)

        try:
            document = fitz.open(path)
        except Exception as exc:
            logger.exception("Failed to open PDF: %s", file_path)
            raise PdfParseError(f"Failed to open PDF: {file_path}") from exc

        try:
            page_count = document.page_count
            pages: list[PageText] = []

            for page_index in range(page_count):
                page_number = page_index + 1
                try:
                    page = document.load_page(page_index)
                    page_text = page.get_text("text") or ""
                except Exception:
                    logger.exception(
                        "Failed to extract text from page %s of %s",
                        page_number,
                        file_path,
                    )
                    page_text = ""
                pages.append(PageText(page_number=page_number, text=page_text))

            text = "\n".join(page.text for page in pages).strip()
            logger.info(
                "Extracted text from %s (%s pages, %s characters)",
                file_path,
                page_count,
                len(text),
            )
            return TextExtractionResult(
                text=text,
                page_count=page_count,
                pages=tuple(pages),
            )
        finally:
            document.close()
