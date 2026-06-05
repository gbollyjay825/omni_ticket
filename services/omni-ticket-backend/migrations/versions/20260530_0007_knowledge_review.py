"""add knowledge article review metadata

Revision ID: 20260530_0007
Revises: 20260529_0006
Create Date: 2026-05-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260530_0007"
down_revision: str | None = "20260529_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_articles",
        sa.Column("submitted_for_review_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_articles",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_articles",
        sa.Column("approved_by", sa.String(length=180), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_articles", "approved_by")
    op.drop_column("knowledge_articles", "approved_at")
    op.drop_column("knowledge_articles", "submitted_for_review_at")
