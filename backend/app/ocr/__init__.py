"""OCR engine abstractions.

Concrete engines (PaddleOCR, …) implement ``OcrEngine`` so the extraction
pipeline can swap providers without changing document workflow code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OcrPageResult:
    """OCR output for a single page."""

    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class OcrDocumentResult:
    """OCR output for a full document."""

    text: str
    page_count: int
    pages: tuple[OcrPageResult, ...]


class OcrEngine(ABC):
    """Interface for optical character recognition engines."""

    @abstractmethod
    def recognize_image(self, image) -> str:
        """Recognize text from a single image (numpy array or file path)."""

    @abstractmethod
    def recognize_pdf(self, file_path: str, *, scale: float = 2.0) -> OcrDocumentResult:
        """Rasterize each PDF page and run OCR, preserving page order."""


class OcrError(Exception):
    """Raised when OCR processing fails."""
