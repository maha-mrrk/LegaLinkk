"""PyMuPDF-based text extraction for digitally generated PDFs."""

from __future__ import annotations

from pathlib import Path

import fitz

from app.core.logging import get_logger
from app.parsers import DocumentParser, PdfParseError, TextExtractionResult

logger = get_logger(__name__)


class PdfParser(DocumentParser):
    """Extract text from digital PDFs using PyMuPDF (``fitz``).

    Scanned / image-only PDFs will typically yield empty text; OCR will be
    plugged in later via a separate parser implementation.
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
            page_texts: list[str] = []

            for page_index in range(page_count):
                try:
                    page = document.load_page(page_index)
                    page_texts.append(page.get_text("text"))
                except Exception:
                    logger.exception(
                        "Failed to extract text from page %s of %s",
                        page_index + 1,
                        file_path,
                    )
                    page_texts.append("")

            text = "\n".join(page_texts).strip()
            logger.info(
                "Extracted text from %s (%s pages, %s characters)",
                file_path,
                page_count,
                len(text),
            )
            return TextExtractionResult(text=text, page_count=page_count)
        finally:
            document.close()
