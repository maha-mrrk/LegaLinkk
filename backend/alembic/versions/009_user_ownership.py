"""Add per-user ownership to documents and conversations.

Revision ID: 009_user_ownership
Revises: 008_document_analyses
Create Date: 2026-07-27 10:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_user_ownership"
down_revision: Union[str, None] = "008_document_analyses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Columns start nullable so existing development/demo data can be assigned
    # before NOT NULL is enforced.
    op.add_column(
        "documents",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    bind = op.get_bind()
    legacy_owner = bind.execute(
        sa.text("SELECT id FROM users ORDER BY created_at ASC, id ASC LIMIT 1")
    ).scalar_one_or_none()
    legacy_rows = bind.execute(
        sa.text(
            "SELECT "
            "(SELECT count(*) FROM documents) + "
            "(SELECT count(*) FROM conversations)"
        )
    ).scalar_one()

    if legacy_rows and legacy_owner is None:
        raise RuntimeError(
            "Cannot assign existing documents/conversations: no user exists"
        )
    if legacy_owner is not None:
        bind.execute(
            sa.text("UPDATE documents SET user_id = :owner WHERE user_id IS NULL"),
            {"owner": legacy_owner},
        )
        bind.execute(
            sa.text(
                "UPDATE conversations SET user_id = :owner WHERE user_id IS NULL"
            ),
            {"owner": legacy_owner},
        )

    op.alter_column("documents", "user_id", nullable=False)
    op.alter_column("conversations", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_documents_user_id_users",
        "documents",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_conversations_user_id_users",
        "conversations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_documents_user_id_upload_date",
        "documents",
        ["user_id", "upload_date"],
    )
    op.create_index(
        "ix_conversations_user_id_updated_at",
        "conversations",
        ["user_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversations_user_id_updated_at",
        table_name="conversations",
    )
    op.drop_index(
        "ix_documents_user_id_upload_date",
        table_name="documents",
    )
    op.drop_constraint(
        "fk_conversations_user_id_users",
        "conversations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_documents_user_id_users",
        "documents",
        type_="foreignkey",
    )
    op.drop_column("conversations", "user_id")
    op.drop_column("documents", "user_id")
