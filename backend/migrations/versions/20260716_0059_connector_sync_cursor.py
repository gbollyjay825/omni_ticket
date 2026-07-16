"""Add durable connector synchronization cursors.

Revision ID: 20260716_0059
Revises: 20260715_0058
"""

from alembic import op
import sqlalchemy as sa


revision = "20260716_0059"
down_revision = "20260715_0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("connector_accounts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "sync_cursor",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("connector_accounts") as batch_op:
        batch_op.drop_column("sync_cursor")
