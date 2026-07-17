"""Normalize extracted PDF / OCR text before chunking."""

from __future__ import annotations

import re

from app.core.logging import get_logger

logger = get_logger(__name__)

_HEADING_RE = re.compile(
    r"^(?:"
    r"(?:ARTICLE|ANNEXE|TITRE|CHAPITRE|SECTION|CLAUSE)\b.*"
    r"|[A-Z0-9][A-Z0-9\s\-''.]{2,80}"
    r"|#{1,6}\s+.+"
    r")$"
)


def clean_text(text: str) -> str:
    """Clean merged document text while preserving likely headings.

    Steps:
    - normalize Windows / legacy line endings
    - collapse runs of spaces / tabs inside lines
    - drop useless empty lines (keep at most one blank line as paragraph break)
    - keep short ALL-CAPS / ARTICLE-style lines as standalone paragraphs
    """
    if not text:
        return ""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\u00a0", " ").replace("\t", " ")

    cleaned_lines: list[str] = []
    for raw_line in normalized.split("\n"):
        line = re.sub(r"[ ]{2,}", " ", raw_line).strip()
        if not line:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue

        if _looks_like_heading(line):
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            cleaned_lines.append(line)
            cleaned_lines.append("")
            continue

        cleaned_lines.append(line)

    # Trim trailing blank lines and collapse 3+ blanks → 1
    collapsed: list[str] = []
    blank_run = 0
    for line in cleaned_lines:
        if line == "":
            blank_run += 1
            if blank_run == 1:
                collapsed.append("")
            continue
        blank_run = 0
        collapsed.append(line)

    result = "\n".join(collapsed).strip()
    logger.debug("Text cleaned: %s → %s characters", len(text), len(result))
    return result


def clean_pages(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Clean each page independently and drop empty pages from the span map."""
    cleaned: list[tuple[int, str]] = []
    for page_number, page_text in pages:
        page_cleaned = clean_text(page_text)
        if page_cleaned:
            cleaned.append((page_number, page_cleaned))
    return cleaned


def _looks_like_heading(line: str) -> bool:
    if len(line) > 100:
        return False
    if _HEADING_RE.match(line):
        # Avoid treating normal sentences as headings just because of caps noise.
        letters = [ch for ch in line if ch.isalpha()]
        if not letters:
            return False
        upper_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
        return upper_ratio >= 0.65 or line.upper().startswith(
            ("ARTICLE", "ANNEXE", "TITRE", "CHAPITRE", "SECTION", "CLAUSE")
        )
    return False
