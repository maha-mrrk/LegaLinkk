"""Create owner-scoped generated PDF document library.

Revision ID: 010_generated_documents
Revises: 009_user_ownership
Create Date: 2026-07-28 10:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010_generated_documents"
down_revision: Union[str, None] = "009_user_ownership"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    kind = postgresql.ENUM(
        "chat_report",
        "analysis_export",
        name="generated_document_kind",
        create_type=False,
    )
    kind.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "generated_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "mime_type",
            sa.String(length=100),
            server_default="application/pdf",
            nullable=False,
        ),
        sa.Column(
            "kind",
            kind,
            server_default="chat_report",
            nullable=False,
        ),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["documents.id"],
            name="fk_generated_documents_source_document",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_generated_documents_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_filename"),
    )
    op.create_index(
        "ix_generated_documents_user_created",
        "generated_documents",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_generated_documents_user_source_created",
        "generated_documents",
        ["user_id", "source_document_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_generated_documents_user_source_created",
        table_name="generated_documents",
    )
    op.drop_index(
        "ix_generated_documents_user_created",
        table_name="generated_documents",
    )
    op.drop_table("generated_documents")
    postgresql.ENUM(
        "chat_report",
        "analysis_export",
        name="generated_document_kind",
    ).drop(op.get_bind(), checkfirst=True)
