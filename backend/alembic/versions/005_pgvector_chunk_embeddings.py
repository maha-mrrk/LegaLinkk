"""Enable pgvector and create chunk_embeddings + index status.

Revision ID: 005_pgvector_chunk_embeddings
Revises: 004_document_chunks_processed
Create Date: 2026-07-17 15:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005_pgvector_chunk_embeddings"
down_revision: Union[str, None] = "004_document_chunks_processed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

index_status = postgresql.ENUM(
    "not_indexed",
    "indexing",
    "indexed",
    "failed",
    name="index_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    index_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "documents",
        sa.Column(
            "index_status",
            index_status,
            nullable=False,
            server_default="not_indexed",
        ),
    )
    op.add_column(
        "documents",
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("indexed_chunk_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "chunk_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column(
            "page_numbers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("extraction_method", sa.String(length=50), nullable=True),
        sa.Column("upload_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("chunk_id", name="uq_chunk_embeddings_chunk_id"),
    )
    op.create_index(
        "ix_chunk_embeddings_document_id",
        "chunk_embeddings",
        ["document_id"],
        unique=False,
    )
    # HNSW cosine index prepares future RAG retrieval (not queried yet).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunk_embeddings_embedding_hnsw "
        "ON chunk_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunk_embeddings_embedding_hnsw")
    op.drop_index("ix_chunk_embeddings_document_id", table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
    op.drop_column("documents", "embedding_model")
    op.drop_column("documents", "indexed_chunk_count")
    op.drop_column("documents", "indexed_at")
    op.drop_column("documents", "index_status")
    index_status.drop(op.get_bind(), checkfirst=True)
