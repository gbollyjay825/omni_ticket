"""Add governed lifecycle metadata to conversation attachments.

Revision ID: 20260715_0057
Revises: 20260715_0056
"""

from alembic import op
import sqlalchemy as sa


revision = "20260715_0057"
down_revision = "20260715_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("conversation_attachments") as batch_op:
        batch_op.add_column(
            sa.Column("scan_result", sa.Text(), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("retained_until", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("deleted_by", sa.String(length=180)))
        batch_op.add_column(sa.Column("deletion_reason", sa.Text()))
        batch_op.add_column(sa.Column("purged_at", sa.DateTime(timezone=True)))
        batch_op.create_index(
            "ix_conversation_attachments_retained_until", ["retained_until"]
        )
        batch_op.create_index("ix_conversation_attachments_deleted_at", ["deleted_at"])
        batch_op.create_index("ix_conversation_attachments_purged_at", ["purged_at"])


def downgrade() -> None:
    with op.batch_alter_table("conversation_attachments") as batch_op:
        batch_op.drop_index("ix_conversation_attachments_purged_at")
        batch_op.drop_index("ix_conversation_attachments_deleted_at")
        batch_op.drop_index("ix_conversation_attachments_retained_until")
        batch_op.drop_column("purged_at")
        batch_op.drop_column("deletion_reason")
        batch_op.drop_column("deleted_by")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("retained_until")
        batch_op.drop_column("scan_result")
