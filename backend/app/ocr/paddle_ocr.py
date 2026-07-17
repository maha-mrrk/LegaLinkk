"""PaddleOCR engine for scanned / image-based PDF pages."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import fitz
import numpy as np

from app.core.logging import get_logger
from app.ocr import OcrDocumentResult, OcrEngine, OcrError, OcrPageResult

logger = get_logger(__name__)


class PaddleOcrEngine(OcrEngine):
    """PaddleOCR-backed engine with multilingual support (EN / FR / AR).

    The underlying PaddleOCR model is loaded lazily and reused across calls.
    """

    def __init__(self, *, lang: str = "en", use_angle_cls: bool = True) -> None:
        self._lang = lang
        self._use_angle_cls = use_angle_cls
        self._ocr: Any | None = None

    def _get_ocr(self) -> Any:
        if self._ocr is None:
            # Must be set before importing paddle (native init reads these).
            import os

            os.environ.setdefault("FLAGS_use_mkldnn", "0")
            os.environ.setdefault("FLAGS_enable_pir_api", "0")
            os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
            os.environ.setdefault("OMP_NUM_THREADS", "1")

            logger.info("Initializing PaddleOCR (lang=%s)", self._lang)
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise OcrError(
                    "PaddleOCR is not installed. Install paddleocr and paddlepaddle."
                ) from exc

            try:
                # show_log / use_gpu vary by paddleocr version — use broad kwargs safely
                kwargs: dict[str, Any] = {
                    "lang": self._lang,
                    "use_angle_cls": self._use_angle_cls,
                }
                try:
                    self._ocr = PaddleOCR(show_log=False, enable_mkldnn=False, **kwargs)
                except TypeError:
                    try:
                        self._ocr = PaddleOCR(show_log=False, **kwargs)
                    except TypeError:
                        self._ocr = PaddleOCR(**kwargs)
            except Exception as exc:
                logger.exception("Failed to initialize PaddleOCR")
                raise OcrError("Failed to initialize PaddleOCR") from exc

            logger.info("PaddleOCR ready (lang=%s)", self._lang)
        return self._ocr

    def recognize_image(self, image: Any) -> str:
        """Run OCR on a numpy image or filesystem path."""
        ocr = self._get_ocr()
        try:
            raw = ocr.ocr(image, cls=self._use_angle_cls)
        except TypeError:
            # Newer paddleocr versions dropped ``cls``
            try:
                raw = ocr.ocr(image)
            except Exception as exc:
                logger.exception("PaddleOCR image recognition failed")
                raise OcrError("PaddleOCR image recognition failed") from exc
        except Exception as exc:
            logger.exception("PaddleOCR image recognition failed")
            raise OcrError("PaddleOCR image recognition failed") from exc

        text = self._lines_from_result(raw)
        logger.debug("PaddleOCR recognized %s characters from image", len(text))
        return text

    def recognize_pdf(self, file_path: str, *, scale: float = 2.0) -> OcrDocumentResult:
        """Convert each PDF page to an image and OCR it in order."""
        path = Path(file_path)
        if not path.is_file():
            message = f"PDF file not found for OCR: {file_path}"
            logger.error(message)
            raise OcrError(message)

        logger.info("Starting PaddleOCR on PDF %s (scale=%.1f)", file_path, scale)

        try:
            document = fitz.open(path)
        except Exception as exc:
            logger.exception("Failed to open PDF for OCR: %s", file_path)
            raise OcrError(f"Failed to open PDF for OCR: {file_path}") from exc

        page_results: list[OcrPageResult] = []
        try:
            page_count = document.page_count
            matrix = fitz.Matrix(scale, scale)

            for page_index in range(page_count):
                page_number = page_index + 1
                logger.info("OCR page %s/%s of %s", page_number, page_count, file_path)
                try:
                    page = document.load_page(page_index)
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                        pix.height, pix.width, pix.n
                    )
                    page_text = self.recognize_image(image)
                except OcrError:
                    logger.exception("OCR failed on page %s of %s", page_number, file_path)
                    page_text = ""
                except Exception:
                    logger.exception(
                        "Unexpected error rasterizing/OCR page %s of %s",
                        page_number,
                        file_path,
                    )
                    page_text = ""

                page_results.append(OcrPageResult(page_number=page_number, text=page_text))
        finally:
            document.close()

        merged = "\n\n".join(page.text for page in page_results if page.text).strip()
        logger.info(
            "PaddleOCR finished %s (%s pages, %s characters)",
            file_path,
            len(page_results),
            len(merged),
        )
        return OcrDocumentResult(
            text=merged,
            page_count=len(page_results),
            pages=tuple(page_results),
        )

    @staticmethod
    def _lines_from_result(raw: Any) -> str:
        """Normalize PaddleOCR 2.x / 3.x result structures into plain text."""
        if raw is None:
            return ""

        lines: list[str] = []

        # PaddleOCR 2.x classic: [[ [box, (text, conf)], ... ]] per image
        if isinstance(raw, list):
            for block in raw:
                if block is None:
                    continue
                if isinstance(block, dict):
                    # Some 3.x-style dict outputs
                    rec_texts = block.get("rec_texts") or block.get("texts")
                    if isinstance(rec_texts, list):
                        lines.extend(str(t) for t in rec_texts if t)
                    continue
                if not isinstance(block, list):
                    continue
                for line in block:
                    if line is None:
                        continue
                    try:
                        # [box, (text, confidence)]
                        text = line[1][0]
                        if text:
                            lines.append(str(text))
                    except (IndexError, TypeError, KeyError):
                        continue
            return "\n".join(lines).strip()

        # Fallback: object with rec_texts attribute
        rec_texts = getattr(raw, "rec_texts", None)
        if isinstance(rec_texts, list):
            return "\n".join(str(t) for t in rec_texts if t).strip()

        return ""


@lru_cache(maxsize=4)
def get_paddle_ocr_engine(lang: str = "en") -> PaddleOcrEngine:
    """Return a cached PaddleOCR engine for the given language code."""
    return PaddleOcrEngine(lang=lang)
