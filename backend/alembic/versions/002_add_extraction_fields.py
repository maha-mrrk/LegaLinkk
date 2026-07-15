"""Add extracted_text and page_count to documents.

Revision ID: 002_add_extraction_fields
Revises: 001_create_documents
Create Date: 2026-07-15 14:35:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_add_extraction_fields"
down_revision: Union[str, None] = "001_create_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("page_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "page_count")
    op.drop_column("documents", "extracted_text")
