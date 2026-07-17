"""Document parser abstractions.

Concrete parsers (digital PDF, OCR pipeline, …) implement ``DocumentParser`` so
the service layer can swap strategies without changing upload workflow code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PageText:
    """Text extracted from a single PDF page (1-based page number)."""

    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class TextExtractionResult:
    """Structured output of a text-extraction pass."""

    text: str
    page_count: int
    extraction_method: str | None = None
    pages: tuple[PageText, ...] = field(default_factory=tuple)


class DocumentParser(ABC):
    """Interface for extracting readable text from a document file."""

    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        """Extract all text from ``file_path`` as a single string."""

    @abstractmethod
    def extract(self, file_path: str) -> TextExtractionResult:
        """Extract text and metadata (e.g. page count) from ``file_path``."""


class PdfParseError(Exception):
    """Raised when a PDF cannot be opened or parsed."""
