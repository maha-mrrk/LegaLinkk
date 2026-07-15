"""Local filesystem helpers for document storage."""

from pathlib import Path
from uuid import uuid4

import aiofiles

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

PDF_MAGIC = b"%PDF"


class DocumentStorage:
    """Stores and deletes PDF files under the configured storage directory."""

    def __init__(self, settings: Settings) -> None:
        self._root = Path(settings.storage_path)

    @property
    def root(self) -> Path:
        return self._root

    def ensure_directory(self) -> None:
        """Create the storage directory if it does not exist."""
        self._root.mkdir(parents=True, exist_ok=True)
        logger.debug("Document storage ready at %s", self._root.resolve())

    def build_stored_filename(self, original_filename: str) -> str:
        """Return a UUID-based filename preserving the original extension."""
        suffix = Path(original_filename).suffix.lower() or ".pdf"
        return f"{uuid4()}{suffix}"

    def resolve_path(self, stored_filename: str) -> Path:
        return self._root / stored_filename

    async def save(self, stored_filename: str, content: bytes) -> Path:
        """Persist file bytes and return the absolute path."""
        self.ensure_directory()
        destination = self.resolve_path(stored_filename)
        async with aiofiles.open(destination, "wb") as handle:
            await handle.write(content)
        logger.info("Stored document file %s (%s bytes)", destination, len(content))
        return destination

    async def delete(self, stored_filename: str) -> None:
        """Remove a stored file if it exists."""
        path = self.resolve_path(stored_filename)
        if path.is_file():
            path.unlink()
            logger.info("Deleted document file %s", path)
        else:
            logger.warning("Document file missing during delete: %s", path)


def is_pdf_content(content: bytes) -> bool:
    """Return True when the byte payload starts with the PDF magic header."""
    return content.startswith(PDF_MAGIC)
