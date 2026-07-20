"""CLI worker: run PaddleOCR in an isolated process.

Invoked as ``python -m app.ocr.paddle_ocr_worker <pdf_path> --lang french --scale 1.0``.
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
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--max-image-side", type=int, default=1280)
    parser.add_argument(
        "--use-angle-cls",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable/disable Paddle angle classifier (disabled by default for low RAM)",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Write the JSON result to this file (avoids stdout pollution)",
    )
    args = parser.parse_args()

    try:
        from app.ocr.paddle_ocr import PaddleOcrEngine

        engine = PaddleOcrEngine(
            lang=args.lang,
            use_angle_cls=args.use_angle_cls,
            max_image_side=args.max_image_side,
        )
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
