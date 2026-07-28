"""Render self-contained HTML documents to PDF with WeasyPrint.

Used by the chat "document generation" mode to turn the grounded HTML report the
LLM produces into a downloadable, print-quality PDF (selectable text, real
layout) — without relying on the browser's print dialog.

Security: the generated documents are always self-contained (inline CSS, no
external resources). To prevent SSRF / local-file access during rendering, the
url fetcher rejects everything except inline ``data:`` URIs.
"""

from __future__ import annotations

import base64
import re
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import AppError, ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

_BRAND_MARKER = 'data-legallink-brand="1"'
_REPORT_CSS = """
<style data-legallink-brand="1">
  @page {
    size: A4;
    margin: 18mm 17mm 20mm;
    @bottom-left {
      content: "LegalLink · Document confidentiel";
      color: #786b76;
      font: 8pt Arial, sans-serif;
    }
    @bottom-right {
      content: "Page " counter(page) " / " counter(pages);
      color: #786b76;
      font: 8pt Arial, sans-serif;
    }
  }
  :root {
    --ll-navy: #360c31;
    --ll-brand: #7c2d6b;
    --ll-brand-dark: #5e1f52;
    --ll-brand-soft: #f6ebf3;
    --ll-gold: #c8a96b;
    --ll-ink: #251c24;
    --ll-muted: #6f626c;
    --ll-border: #ded4dc;
  }
  html { background: #fff !important; }
  body {
    margin: 0 !important;
    padding: 0 !important;
    color: var(--ll-ink) !important;
    background: #fff !important;
    font-family: "Segoe UI", Arial, sans-serif !important;
    font-size: 10.5pt !important;
    line-height: 1.55 !important;
  }
  .legallink-report-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: 0 0 22px;
    padding: 14px 18px;
    border-radius: 10px;
    background: linear-gradient(135deg, var(--ll-navy), var(--ll-brand));
    color: #fff;
    break-inside: avoid;
  }
  .legallink-report-logo {
    width: 44px;
    height: 44px;
    object-fit: contain;
    flex: 0 0 44px;
  }
  .legallink-report-brand {
    display: block;
    font-size: 17pt;
    font-weight: 750;
    letter-spacing: .2px;
  }
  .legallink-report-tagline {
    display: block;
    margin-top: 1px;
    color: #f5eaf2;
    font-size: 8.5pt;
    letter-spacing: .45px;
    text-transform: uppercase;
  }
  .legallink-report-content { width: 100%; }
  .legallink-report-content h1 {
    margin: 0 0 18px !important;
    color: var(--ll-navy) !important;
    font-size: 23pt !important;
    line-height: 1.18 !important;
    letter-spacing: -.35px;
    border-bottom: 3px solid var(--ll-brand) !important;
    padding-bottom: 9px !important;
  }
  .legallink-report-content h2 {
    margin: 22px 0 10px !important;
    padding-left: 10px !important;
    color: var(--ll-brand-dark) !important;
    font-size: 15pt !important;
    line-height: 1.25 !important;
    border-left: 4px solid var(--ll-brand) !important;
    break-after: avoid;
  }
  .legallink-report-content h3 {
    margin: 16px 0 7px !important;
    color: var(--ll-navy) !important;
    font-size: 12pt !important;
    break-after: avoid;
  }
  .legallink-report-content p { margin: 0 0 9px !important; }
  .legallink-report-content ul,
  .legallink-report-content ol {
    margin: 7px 0 12px 20px !important;
    padding: 0 !important;
  }
  .legallink-report-content li { margin-bottom: 4px !important; }
  .legallink-report-content strong { color: var(--ll-navy); }
  .legallink-report-content a { color: var(--ll-brand); }
  .legallink-report-content blockquote {
    margin: 12px 0 !important;
    padding: 10px 14px !important;
    border-left: 4px solid var(--ll-gold) !important;
    background: #fbf8f2 !important;
    color: #51464e !important;
  }
  .legallink-report-content table {
    width: 100% !important;
    margin: 13px 0 18px !important;
    border-collapse: collapse !important;
    table-layout: auto !important;
    font-size: 8.5pt !important;
  }
  .legallink-report-content thead { display: table-header-group; }
  .legallink-report-content tr { break-inside: avoid; }
  .legallink-report-content th {
    padding: 8px 7px !important;
    border: 1px solid var(--ll-navy) !important;
    background: var(--ll-navy) !important;
    color: #fff !important;
    text-align: left !important;
    vertical-align: top !important;
  }
  .legallink-report-content td {
    padding: 7px !important;
    border: 1px solid var(--ll-border) !important;
    vertical-align: top !important;
    overflow-wrap: anywhere;
  }
  .legallink-report-content tbody tr:nth-child(even) td {
    background: #faf7f9 !important;
  }
  .legallink-report-content hr {
    margin: 18px 0 !important;
    border: 0 !important;
    border-top: 1px solid var(--ll-border) !important;
  }
  .legallink-report-footer {
    margin-top: 24px;
    padding-top: 9px;
    border-top: 1px solid var(--ll-border);
    color: var(--ll-muted);
    font-size: 8pt;
    text-align: center;
  }
  img { max-width: 100%; }
  @media print {
    .legallink-report-header {
      print-color-adjust: exact;
      -webkit-print-color-adjust: exact;
    }
  }
</style>
"""


class PdfRenderError(AppError):
    """Raised when HTML→PDF rendering fails."""

    def __init__(self, message: str = "Failed to render the document to PDF") -> None:
        super().__init__(message, status_code=500, code="pdf_render_error")


def _blocking_url_fetcher(url: str):
    """Allow only inline ``data:`` URIs; block all network/file access."""
    if url.startswith("data:"):
        from weasyprint.urls import default_url_fetcher

        return default_url_fetcher(url)
    raise ValueError(f"Blocked external resource during PDF rendering: {url[:80]}")


@lru_cache
def _logo_data_uri() -> str | None:
    path = Path(get_settings().brand_logo_path)
    try:
        content = path.read_bytes()
    except OSError:
        logger.warning("Brand logo not found at %s", path)
        return None
    return f"data:image/png;base64,{base64.b64encode(content).decode('ascii')}"


def brand_report_html(html: str) -> str:
    """Apply the canonical LegalLink report shell to arbitrary report HTML."""
    cleaned = (html or "").strip()
    if not cleaned or _BRAND_MARKER in cleaned:
        return cleaned

    logo_uri = _logo_data_uri()
    logo = (
        f'<img class="legallink-report-logo" src="{logo_uri}" alt="LegalLink">'
        if logo_uri
        else ""
    )
    header = (
        '<header class="legallink-report-header">'
        f"{logo}"
        "<div>"
        '<span class="legallink-report-brand">LegalLink</span>'
        '<span class="legallink-report-tagline">'
        "Intelligence juridique · Rapport professionnel"
        "</span>"
        "</div>"
        "</header>"
    )
    footer = (
        '<footer class="legallink-report-footer">'
        "Généré par LegalLink · Document confidentiel"
        "</footer>"
    )

    if re.search(r"</head\s*>", cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(
            r"</head\s*>",
            f"{_REPORT_CSS}</head>",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )
    elif re.search(r"<html[^>]*>", cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(
            r"(<html[^>]*>)",
            rf"\1<head>{_REPORT_CSS}</head>",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        cleaned = f"<!DOCTYPE html><html><head>{_REPORT_CSS}</head><body>{cleaned}</body></html>"

    body_match = re.search(
        r"<body([^>]*)>(.*?)</body\s*>",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if body_match:
        body = body_match.group(2)
        replacement = (
            f"<body{body_match.group(1)}>{header}"
            f'<main class="legallink-report-content">{body}</main>'
            f"{footer}</body>"
        )
        cleaned = (
            cleaned[: body_match.start()]
            + replacement
            + cleaned[body_match.end() :]
        )
    return cleaned


def render_html_to_pdf(html: str) -> bytes:
    """Render a self-contained HTML string to PDF bytes.

    Runs the (synchronous, CPU-bound) WeasyPrint pipeline; callers should invoke
    it via ``asyncio.to_thread`` to avoid blocking the event loop.
    """
    if not (html or "").strip():
        raise ValidationError("Cannot render an empty document to PDF")

    try:
        from weasyprint import HTML
    except ImportError as exc:  # pragma: no cover - depends on image build
        logger.exception("WeasyPrint is not installed")
        raise PdfRenderError(
            "Le générateur de PDF n'est pas disponible sur le serveur."
        ) from exc

    try:
        document = HTML(
            string=brand_report_html(html),
            url_fetcher=_blocking_url_fetcher,
        )
        pdf_bytes = document.write_pdf()
    except Exception as exc:
        logger.exception("HTML→PDF rendering failed")
        raise PdfRenderError() from exc

    logger.info("Rendered document to PDF (%s bytes).", len(pdf_bytes))
    return pdf_bytes
