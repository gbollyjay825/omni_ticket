"""Add Freshdesk-parity contact profile and lifecycle fields.

Revision ID: 20260714_0055
Revises: 20260714_0054
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714_0055"
down_revision = "20260714_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("customers") as batch_op:
        batch_op.add_column(
            sa.Column("job_title", sa.String(length=180), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column(
                "timezone",
                sa.String(length=80),
                nullable=False,
                server_default="Africa/Lagos",
            )
        )
        batch_op.add_column(
            sa.Column("language", sa.String(length=80), nullable=False, server_default="English")
        )
        batch_op.add_column(
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(sa.Column("merged_into_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_customers_merged_into_id_customers",
            "customers",
            ["merged_into_id"],
            ["id"],
        )
        batch_op.create_index("ix_customers_active", ["active"])
        batch_op.create_index("ix_customers_merged_into_id", ["merged_into_id"])


def downgrade() -> None:
    with op.batch_alter_table("customers") as batch_op:
        batch_op.drop_index("ix_customers_merged_into_id")
        batch_op.drop_index("ix_customers_active")
        batch_op.drop_constraint("fk_customers_merged_into_id_customers", type_="foreignkey")
        batch_op.drop_column("merged_into_id")
        batch_op.drop_column("active")
        batch_op.drop_column("language")
        batch_op.drop_column("timezone")
        batch_op.drop_column("job_title")
