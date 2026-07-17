"""Automatic PDF text extraction: digital parser first, OCR fallback."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.document import ExtractionMethod
from app.ocr import OcrEngine, OcrError
from app.ocr.paddle_ocr import get_paddle_ocr_engine
from app.ocr.subprocess_runner import run_paddle_ocr_subprocess
from app.parsers import DocumentParser, PageText, PdfParseError, TextExtractionResult
from app.parsers.pdf_parser import PdfParser

logger = get_logger(__name__)


class ExtractionError(Exception):
    """Raised when both digital parsing and OCR fail to produce usable text."""


class ExtractionPipeline(DocumentParser):
    """Decide automatically between PyMuPDF text extraction and PaddleOCR.

    Workflow:
    1. Extract with the digital PDF parser.
    2. If text is sufficient → return it (``pdf_parser``).
    3. Otherwise treat as scanned → rasterize + OCR (``paddle_ocr``).
    """

    def __init__(
        self,
        *,
        pdf_parser: PdfParser | None = None,
        ocr_engine: OcrEngine | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._pdf_parser = pdf_parser or PdfParser()
        self._ocr_engine = ocr_engine

    def _get_ocr_engine(self) -> OcrEngine:
        if self._ocr_engine is None:
            self._ocr_engine = get_paddle_ocr_engine(self._settings.ocr_lang)
        return self._ocr_engine

    def is_scanned_pdf(self, text: str, page_count: int) -> bool:
        """Return True when digital text looks insufficient for a readable PDF."""
        stripped = (text or "").strip()
        if page_count <= 0:
            logger.info("Treating PDF as scanned: page_count=%s", page_count)
            return True
        if not stripped:
            logger.info("Treating PDF as scanned: no extractable digital text")
            return True

        chars_per_page = len(stripped) / page_count
        threshold = self._settings.ocr_min_chars_per_page
        is_scanned = chars_per_page < threshold
        logger.info(
            "Scanned-PDF check: chars=%s pages=%s chars/page=%.1f threshold=%s → %s",
            len(stripped),
            page_count,
            chars_per_page,
            threshold,
            "scanned" if is_scanned else "digital",
        )
        return is_scanned

    def extract_text_with_ocr(self, file_path: str) -> TextExtractionResult:
        """Rasterize PDF pages and extract text with the configured OCR engine.

        OCR runs in an isolated subprocess so a native crash (SIGSEGV) cannot
        take down the FastAPI/uvicorn worker.
        """
        logger.info("OCR started for %s (isolated subprocess)", file_path)
        try:
            if self._ocr_engine is not None:
                ocr_result = self._ocr_engine.recognize_pdf(
                    file_path,
                    scale=self._settings.ocr_render_scale,
                )
            else:
                ocr_result = run_paddle_ocr_subprocess(
                    file_path,
                    lang=self._settings.ocr_lang,
                    scale=self._settings.ocr_render_scale,
                )
        except OcrError as exc:
            logger.exception("OCR extraction failed for %s", file_path)
            raise ExtractionError(f"OCR extraction failed for {file_path}") from exc

        pages = tuple(
            PageText(page_number=page.page_number, text=page.text)
            for page in ocr_result.pages
        )
        logger.info(
            "OCR finished for %s (%s pages, %s characters)",
            file_path,
            ocr_result.page_count,
            len(ocr_result.text or ""),
        )
        return TextExtractionResult(
            text=ocr_result.text,
            page_count=ocr_result.page_count,
            extraction_method=ExtractionMethod.PADDLE_OCR.value,
            pages=pages,
        )

    def extract_text(self, file_path: str) -> str:
        """Run the full pipeline and return only the merged text."""
        return self.extract(file_path).text

    def extract(self, file_path: str) -> TextExtractionResult:
        """Try digital extraction, then OCR if the PDF appears scanned."""
        logger.info("Parsing started for %s", file_path)

        try:
            digital = self._pdf_parser.extract(file_path)
        except PdfParseError as exc:
            logger.warning(
                "Digital PDF parse failed for %s — falling back to OCR: %s",
                file_path,
                exc,
            )
            if not self._settings.ocr_enabled:
                raise ExtractionError(
                    f"Digital parse failed and OCR is disabled: {file_path}"
                ) from exc
            return self.extract_text_with_ocr(file_path)

        if not self.is_scanned_pdf(digital.text, digital.page_count):
            logger.info(
                "Using pdf_parser for %s (%s pages, %s characters)",
                file_path,
                digital.page_count,
                len(digital.text),
            )
            return TextExtractionResult(
                text=digital.text,
                page_count=digital.page_count,
                extraction_method=ExtractionMethod.PDF_PARSER.value,
                pages=digital.pages,
            )

        if not self._settings.ocr_enabled:
            logger.warning(
                "PDF looks scanned but OCR is disabled — returning digital text for %s",
                file_path,
            )
            return TextExtractionResult(
                text=digital.text,
                page_count=digital.page_count,
                extraction_method=ExtractionMethod.PDF_PARSER.value,
                pages=digital.pages,
            )

        logger.info("PDF classified as scanned — switching to PaddleOCR for %s", file_path)
        try:
            return self.extract_text_with_ocr(file_path)
        except ExtractionError as exc:
            logger.exception(
                "OCR failed after scanned detection for %s",
                file_path,
            )
            # Do not mislabel as pdf_parser — OCR was selected and failed.
            raise ExtractionError(
                f"Scanned PDF detected but OCR failed for {file_path}"
            ) from exc
