"""add attachment lifecycle retention fields

Revision ID: 20260604_0014
Revises: 20260604_0013
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260604_0014"
down_revision: str | None = "20260604_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "attachments",
        sa.Column(
            "lifecycle_status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column("attachments", sa.Column("retained_until", sa.DateTime(timezone=True)))
    op.add_column("attachments", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.add_column("attachments", sa.Column("deleted_by", sa.String(length=180)))
    op.add_column("attachments", sa.Column("deletion_reason", sa.Text()))
    op.add_column("attachments", sa.Column("purged_at", sa.DateTime(timezone=True)))
    op.create_index("ix_attachments_lifecycle_status", "attachments", ["lifecycle_status"])
    op.create_index("ix_attachments_retained_until", "attachments", ["retained_until"])
    op.create_index("ix_attachments_deleted_at", "attachments", ["deleted_at"])
    op.create_index("ix_attachments_purged_at", "attachments", ["purged_at"])


def downgrade() -> None:
    op.drop_index("ix_attachments_purged_at", table_name="attachments")
    op.drop_index("ix_attachments_deleted_at", table_name="attachments")
    op.drop_index("ix_attachments_retained_until", table_name="attachments")
    op.drop_index("ix_attachments_lifecycle_status", table_name="attachments")
    op.drop_column("attachments", "purged_at")
    op.drop_column("attachments", "deletion_reason")
    op.drop_column("attachments", "deleted_by")
    op.drop_column("attachments", "deleted_at")
    op.drop_column("attachments", "retained_until")
    op.drop_column("attachments", "lifecycle_status")
