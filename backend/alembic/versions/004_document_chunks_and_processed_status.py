"""Add document_chunks table and processed document status.

Revision ID: 004_document_chunks_processed
Revises: 003_add_extraction_method
Create Date: 2026-07-17 14:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_document_chunks_processed"
down_revision: Union[str, None] = "003_add_extraction_method"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL requires new enum values to be committed before use.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'processed'")

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_id_chunk_index",
        ),
    )
    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
        unique=False,
    )

    op.execute(
        "UPDATE documents SET status = 'processed' WHERE status = 'completed'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE documents SET status = 'completed' WHERE status = 'processed'"
    )
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    # Enum value 'processed' is left in place — PostgreSQL cannot easily drop enum values.
