"""add market-scoped csat surveys

Revision ID: 20260606_0029
Revises: 20260606_0028
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0029"
down_revision: str | None = "20260606_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "csat_surveys",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("question", sa.String(length=300), nullable=False),
        sa.Column("scale", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("channels", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_csat_survey_market_name"),
    )
    op.create_index("ix_csat_surveys_market_id", "csat_surveys", ["market_id"])
    op.create_index("ix_csat_surveys_active", "csat_surveys", ["active"])


def downgrade() -> None:
    op.drop_index("ix_csat_surveys_active", table_name="csat_surveys")
    op.drop_index("ix_csat_surveys_market_id", table_name="csat_surveys")
    op.drop_table("csat_surveys")
