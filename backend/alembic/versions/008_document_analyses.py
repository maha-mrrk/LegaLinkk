"""Create persisted document analyses.

Revision ID: 008_document_analyses
Revises: 007_create_users
Create Date: 2026-07-27 09:40:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_document_analyses"
down_revision: Union[str, None] = "007_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

analysis_status = postgresql.ENUM(
    "processing",
    "completed",
    "failed",
    name="analysis_status",
    create_type=False,
)


def upgrade() -> None:
    analysis_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "document_analyses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            analysis_status,
            server_default="processing",
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "analysis_version",
            sa.String(length=32),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "request_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.UniqueConstraint(
            "document_id",
            name="uq_document_analyses_document_id",
        ),
    )
    op.create_index(
        "ix_document_analyses_document_id",
        "document_analyses",
        ["document_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_analyses_document_id",
        table_name="document_analyses",
    )
    op.drop_table("document_analyses")
    analysis_status.drop(op.get_bind(), checkfirst=True)
