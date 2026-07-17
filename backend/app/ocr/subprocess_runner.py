"""Run PaddleOCR in a subprocess so native crashes cannot kill the API worker."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from app.core.logging import get_logger
from app.ocr import OcrDocumentResult, OcrError, OcrPageResult

logger = get_logger(__name__)


def _parse_worker_stdout(stdout: str) -> dict:
    """Parse worker JSON even when PaddleOCR polluted stdout with progress bars."""
    raw = (stdout or "").strip()
    if not raw:
        raise OcrError("OCR subprocess produced no output")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    for line in reversed(raw.splitlines()):
        candidate = line.strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    start = raw.rfind("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise OcrError("OCR subprocess returned invalid JSON")


def _load_payload(*, output_json: Path, stdout: str) -> dict:
    """Prefer the dedicated JSON file; fall back to parsing stdout."""
    if output_json.is_file():
        try:
            return json.loads(output_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read OCR result file %s: %s", output_json, exc)

    return _parse_worker_stdout(stdout)


def run_paddle_ocr_subprocess(
    file_path: str,
    *,
    lang: str = "en",
    scale: float = 2.0,
    timeout_seconds: int = 600,
) -> OcrDocumentResult:
    """Execute OCR in a child process and return structured results."""
    with tempfile.TemporaryDirectory(prefix="legallink-ocr-") as tmp_dir:
        output_json = Path(tmp_dir) / "result.json"
        cmd = [
            sys.executable,
            "-m",
            "app.ocr.paddle_ocr_worker",
            file_path,
            "--lang",
            lang,
            "--scale",
            str(scale),
            "--output-json",
            str(output_json),
        ]
        logger.info("Starting isolated OCR subprocess for %s", file_path)

        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OcrError(f"OCR subprocess timed out for {file_path}") from exc

        if completed.returncode < 0:
            signal_num = -completed.returncode
            logger.error(
                "OCR subprocess killed by signal %s for %s (API worker preserved)",
                signal_num,
                file_path,
            )
            raise OcrError(
                f"OCR process crashed (signal {signal_num}). The API remains available."
            )

        try:
            payload = _load_payload(
                output_json=output_json,
                stdout=completed.stdout or "",
            )
        except OcrError:
            logger.error(
                "OCR subprocess produced no usable JSON (code=%s): %s",
                completed.returncode,
                (completed.stderr or "")[-500:],
            )
            raise

        if not payload.get("ok"):
            raise OcrError(payload.get("error") or "OCR subprocess failed")

        pages_raw = payload.get("pages") or []
        pages: list[OcrPageResult] = []
        if isinstance(pages_raw, list):
            for item in pages_raw:
                if not isinstance(item, dict):
                    continue
                try:
                    pages.append(
                        OcrPageResult(
                            page_number=int(item.get("page_number") or 0),
                            text=str(item.get("text") or ""),
                        )
                    )
                except (TypeError, ValueError):
                    continue

        return OcrDocumentResult(
            text=str(payload.get("text") or ""),
            page_count=int(payload.get("page_count") or 0),
            pages=tuple(pages),
        )
