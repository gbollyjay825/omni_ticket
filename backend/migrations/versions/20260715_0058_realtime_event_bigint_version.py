"""Store realtime event versions as 64-bit integers.

Revision ID: 20260715_0058
Revises: 20260715_0057
"""

from alembic import op
import sqlalchemy as sa


revision = "20260715_0058"
down_revision = "20260715_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("realtime_events") as batch_op:
        batch_op.alter_column(
            "version",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("realtime_events") as batch_op:
        batch_op.alter_column(
            "version",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=False,
        )
