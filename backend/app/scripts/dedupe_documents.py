"""Remove duplicate uploaded documents that pollute library-wide retrieval.

Two documents are treated as duplicates when they share the same original
filename **and** file size (there is no content-hash column, so this is the best
available heuristic for "the same file uploaded twice"). For each duplicate
group we keep a single canonical document — preferring an INDEXED copy, then the
earliest upload — and delete the rest. Deletion cascades to chunks and
embeddings (ORM ``delete-orphan`` + FK ``ON DELETE CASCADE``) and removes the
stored PDF from disk.

Safe by default: it only prints a plan. Pass ``--apply`` to actually delete.

Usage (inside the backend container)::

    docker compose exec backend python -m app.scripts.dedupe_documents
    docker compose exec backend python -m app.scripts.dedupe_documents --apply
"""

from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import task_session
from app.models.document import Document
from app.models.embedding import IndexStatus
from app.repositories.document import DocumentRepository
from app.utils.storage import DocumentStorage

logger = get_logger(__name__)


def _keep_priority(doc: Document) -> tuple[int, object]:
    """Sort key: keep an INDEXED copy first, then the earliest upload."""
    indexed_first = 0 if doc.index_status == IndexStatus.INDEXED else 1
    return (indexed_first, doc.upload_date)


async def _load_all() -> list[Document]:
    async with task_session() as session:
        result = await session.execute(select(Document))
        return list(result.scalars().all())


async def _delete_one(document_id: UUID) -> None:
    """Delete a single document (cascades to chunks/embeddings) + its file."""
    async with task_session() as session:
        repo = DocumentRepository(session)
        document = await repo.get_by_id(document_id)
        if document is None:
            return
        stored_filename = document.stored_filename
        await repo.delete(document)
        await session.commit()
    await DocumentStorage(get_settings()).delete(stored_filename)


async def _run(apply: bool) -> None:
    documents = await _load_all()

    groups: dict[tuple[str, int], list[Document]] = {}
    for doc in documents:
        groups.setdefault((doc.original_filename, doc.file_size), []).append(doc)

    to_delete: list[UUID] = []
    for (name, size), docs in sorted(groups.items()):
        if len(docs) < 2:
            continue
        ordered = sorted(docs, key=_keep_priority)
        keep, dupes = ordered[0], ordered[1:]
        print(
            f"- '{name}' ({size} bytes): {len(docs)} copies "
            f"→ keep {keep.id}, remove {len(dupes)}"
        )
        to_delete.extend(d.id for d in dupes)

    print(
        f"\nDocuments total: {len(documents)} | duplicate copies to remove: "
        f"{len(to_delete)}"
    )
    if not to_delete:
        print("Nothing to do — no duplicates found.")
        return
    if not apply:
        print("\nDRY-RUN — nothing was deleted. Re-run with --apply to remove.")
        return

    deleted = 0
    for document_id in to_delete:
        try:
            await _delete_one(document_id)
            deleted += 1
        except Exception as exc:  # keep going on individual failures
            print(f"  ! failed to delete {document_id}: {exc}")
    print(f"\nDeleted {deleted}/{len(to_delete)} duplicate documents.")


def main() -> None:
    apply = "--apply" in sys.argv[1:]
    asyncio.run(_run(apply))


if __name__ == "__main__":
    main()
