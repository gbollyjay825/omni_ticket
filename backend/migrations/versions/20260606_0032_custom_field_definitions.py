"""add market-scoped custom field definitions (contact/company)

Revision ID: 20260606_0032
Revises: 20260606_0031
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0032"
down_revision: str | None = "20260606_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custom_field_definitions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("entity", sa.String(length=20), nullable=False, server_default="contact"),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("field_type", sa.String(length=32), nullable=False, server_default="text"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("options", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("help_text", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "entity", "key", name="uq_custom_field_market_entity_key"),
    )
    op.create_index(
        "ix_custom_field_definitions_market_id", "custom_field_definitions", ["market_id"]
    )
    op.create_index("ix_custom_field_definitions_entity", "custom_field_definitions", ["entity"])
    op.create_index("ix_custom_field_definitions_active", "custom_field_definitions", ["active"])


def downgrade() -> None:
    op.drop_index("ix_custom_field_definitions_active", table_name="custom_field_definitions")
    op.drop_index("ix_custom_field_definitions_entity", table_name="custom_field_definitions")
    op.drop_index("ix_custom_field_definitions_market_id", table_name="custom_field_definitions")
    op.drop_table("custom_field_definitions")
