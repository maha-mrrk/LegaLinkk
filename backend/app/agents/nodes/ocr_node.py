"""OCRNode — graph wrapper around the OCR engine service."""

from __future__ import annotations

import asyncio

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes._state_utils import ensure_metadata, source_path
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.document import ExtractionMethod
from app.ocr import OcrEngine
from app.ocr.paddle_ocr import get_paddle_ocr_engine
from app.state.graph_state import GraphState

logger = get_logger(__name__)


class OCRNode(BaseGraphAgent):
    """Extract text from a scanned PDF by delegating to an ``OcrEngine``.

    Orchestration only: OCR logic lives in the injected engine
    (PaddleOCR by default). The node just maps GraphState in and out.
    """

    def __init__(
        self,
        ocr_engine: OcrEngine | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._ocr_engine = ocr_engine or get_paddle_ocr_engine(
            self._settings.ocr_lang,
            self._settings.ocr_use_angle_cls,
            self._settings.ocr_max_image_side,
        )

    @property
    def name(self) -> str:
        return "ocr"

    @property
    def description(self) -> str:
        return "Extract text from a scanned PDF via the OCR engine service."

    async def execute(self, state: GraphState) -> GraphState:
        file_path = source_path(state)
        if not file_path:
            raise ValueError("OCRNode requires metadata['file_path'] or filename")

        logger.info("OCRNode: running OCR on %s", file_path)
        result = await asyncio.to_thread(
            self._ocr_engine.recognize_pdf,
            file_path,
            scale=self._settings.ocr_render_scale,
        )

        state["extracted_text"] = result.text
        metadata = ensure_metadata(state)
        metadata["page_count"] = result.page_count
        metadata["extraction_method"] = ExtractionMethod.PADDLE_OCR.value
        metadata["pages"] = [(page.page_number, page.text) for page in result.pages]
        return state
