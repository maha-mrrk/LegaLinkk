"""Add extraction_method to documents.

Revision ID: 003_add_extraction_method
Revises: 002_add_extraction_fields
Create Date: 2026-07-15 14:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_add_extraction_method"
down_revision: Union[str, None] = "002_add_extraction_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

extraction_method = postgresql.ENUM(
    "pdf_parser",
    "paddle_ocr",
    name="extraction_method",
    create_type=False,
)


def upgrade() -> None:
    extraction_method.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "documents",
        sa.Column("extraction_method", extraction_method, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "extraction_method")
    extraction_method.drop(op.get_bind(), checkfirst=True)
