"""Unit tests for text cleaning and semantic chunking."""

from uuid import uuid4

from app.services.chunker import SemanticChunker
from app.services.text_cleaner import clean_text


def test_clean_text_collapses_spaces_and_blank_lines() -> None:
    raw = "Hello   world\n\n\n\nARTICLE 1\n\nNext   paragraph.\n\n\n"
    cleaned = clean_text(raw)
    assert "  " not in cleaned
    assert "\n\n\n" not in cleaned
    assert "ARTICLE 1" in cleaned
    assert cleaned.startswith("Hello world")


def test_chunker_respects_size_and_non_empty() -> None:
    paragraphs = [f"Paragraph {i}. " + ("lorem ipsum " * 20) for i in range(12)]
    text = "\n\n".join(paragraphs)
    chunker = SemanticChunker(chunk_size=900, chunk_overlap=175)
    drafts = chunker.chunk_document(
        document_id=uuid4(),
        text=text,
        pages=None,
        extraction_method="pdf_parser",
    )
    assert drafts
    assert all(draft.text.strip() for draft in drafts)
    assert all(draft.metadata["chunk_length"] <= 1100 for draft in drafts)
    assert any(draft.metadata["chunk_length"] >= 400 for draft in drafts)
    assert drafts[0].metadata["chunk_index"] == 0
    assert drafts[0].metadata["extraction_method"] == "pdf_parser"


def test_chunker_tracks_page_numbers() -> None:
    pages = [
        (1, "Page one content. " * 40),
        (2, "Page two content. " * 40),
        (3, "Page three content. " * 40),
    ]
    chunker = SemanticChunker(chunk_size=500, chunk_overlap=100)
    drafts = chunker.chunk_document(
        document_id=uuid4(),
        text="",
        pages=pages,
        extraction_method="paddle_ocr",
    )
    assert drafts
    assert any(draft.page_numbers for draft in drafts)
    assert all(
        page >= 1 for draft in drafts for page in draft.page_numbers
    )
