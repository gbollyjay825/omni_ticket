"""add import reconciliation and cutover gates

Revision ID: 20260714_0051
Revises: 20260714_0050
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260714_0051"
down_revision: str | None = "20260714_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_reconciliations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_checksum", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sample_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_attachments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.String(length=180), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_id",
            "provider",
            "entity_type",
            name="uq_import_reconciliation_market_provider_entity",
        ),
    )
    for column in ("market_id", "provider", "entity_type", "source_snapshot_at"):
        op.create_index(
            f"ix_import_reconciliations_{column}",
            "import_reconciliations",
            [column],
        )

    op.create_table(
        "import_cutover_decisions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("decided_by", sa.String(length=180), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rollback_until", sa.DateTime(timezone=True)),
        sa.Column("readiness_hash", sa.String(length=64), nullable=False),
        sa.Column("readiness_snapshot", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("market_id", "status", "decided_at"):
        op.create_index(
            f"ix_import_cutover_decisions_{column}",
            "import_cutover_decisions",
            [column],
        )


def downgrade() -> None:
    op.drop_table("import_cutover_decisions")
    op.drop_table("import_reconciliations")
