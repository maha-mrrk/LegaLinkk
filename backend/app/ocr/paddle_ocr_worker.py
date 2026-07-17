"""CLI worker: run PaddleOCR in an isolated process.

Invoked as ``python -m app.ocr.paddle_ocr_worker <pdf_path> --lang en --scale 2.0``.
Writes a JSON result file (and a single JSON line to stdout). A segfault here
kills only this process.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _write_payload(payload: dict, output_json: str | None) -> None:
    raw = json.dumps(payload, ensure_ascii=False)
    if output_json:
        Path(output_json).write_text(raw + "\n", encoding="utf-8")
    sys.stdout.write(raw + "\n")
    sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolated PaddleOCR worker")
    parser.add_argument("file_path", help="Path to the PDF file")
    parser.add_argument("--lang", default="en")
    parser.add_argument("--scale", type=float, default=2.0)
    parser.add_argument(
        "--output-json",
        default=None,
        help="Write the JSON result to this file (avoids stdout pollution)",
    )
    args = parser.parse_args()

    try:
        from app.ocr.paddle_ocr import PaddleOcrEngine

        engine = PaddleOcrEngine(lang=args.lang)
        result = engine.recognize_pdf(args.file_path, scale=args.scale)
        _write_payload(
            {
                "ok": True,
                "text": result.text,
                "page_count": result.page_count,
                "pages": [
                    {"page_number": page.page_number, "text": page.text}
                    for page in result.pages
                ],
            },
            args.output_json,
        )
        return 0
    except Exception as exc:
        _write_payload({"ok": False, "error": str(exc)}, args.output_json)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
