"""add import runs, cursors, external mappings, and customer identities

Revision ID: 20260714_0045
Revises: 20260714_0044
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260714_0045"
down_revision: str | None = "20260714_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_identities",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="omni"),
        sa.Column("identity_type", sa.String(length=40), nullable=False),
        sa.Column("normalized_value", sa.String(length=500), nullable=False),
        sa.Column("display_value", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("identity_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_id",
            "provider",
            "identity_type",
            "normalized_value",
            name="uq_customer_identity_market_provider_type_value",
        ),
    )
    op.create_index("ix_customer_identities_market_id", "customer_identities", ["market_id"])
    op.create_index("ix_customer_identities_customer_id", "customer_identities", ["customer_id"])
    op.create_index("ix_customer_identities_provider", "customer_identities", ["provider"])
    op.create_index("ix_customer_identities_identity_type", "customer_identities", ["identity_type"])
    op.create_index(
        "ix_customer_identities_normalized_value",
        "customer_identities",
        ["normalized_value"],
    )

    op.create_table(
        "import_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_by", sa.String(length=180), nullable=False, server_default="migration-cli"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_cursor", sa.JSON(), nullable=False),
        sa.Column("next_cursor", sa.JSON(), nullable=False),
        sa.Column("statistics", sa.JSON(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_runs_market_id", "import_runs", ["market_id"])
    op.create_index("ix_import_runs_provider", "import_runs", ["provider"])
    op.create_index("ix_import_runs_mode", "import_runs", ["mode"])
    op.create_index("ix_import_runs_status", "import_runs", ["status"])

    op.create_table(
        "import_cursors",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("resource", sa.String(length=80), nullable=False),
        sa.Column("cursor", sa.JSON(), nullable=False),
        sa.Column("checkpoint_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_id",
            "provider",
            "resource",
            name="uq_import_cursor_market_provider_resource",
        ),
    )
    op.create_index("ix_import_cursors_market_id", "import_cursors", ["market_id"])
    op.create_index("ix_import_cursors_provider", "import_cursors", ["provider"])
    op.create_index("ix_import_cursors_resource", "import_cursors", ["resource"])

    op.create_table(
        "external_id_mappings",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("internal_id", sa.String(length=64), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("mapping_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_id",
            "provider",
            "entity_type",
            "external_id",
            name="uq_external_mapping_market_provider_entity_external",
        ),
    )
    op.create_index("ix_external_id_mappings_market_id", "external_id_mappings", ["market_id"])
    op.create_index("ix_external_id_mappings_provider", "external_id_mappings", ["provider"])
    op.create_index("ix_external_id_mappings_entity_type", "external_id_mappings", ["entity_type"])
    op.create_index("ix_external_id_mappings_external_id", "external_id_mappings", ["external_id"])
    op.create_index("ix_external_id_mappings_internal_id", "external_id_mappings", ["internal_id"])


def downgrade() -> None:
    op.drop_index("ix_external_id_mappings_internal_id", table_name="external_id_mappings")
    op.drop_index("ix_external_id_mappings_external_id", table_name="external_id_mappings")
    op.drop_index("ix_external_id_mappings_entity_type", table_name="external_id_mappings")
    op.drop_index("ix_external_id_mappings_provider", table_name="external_id_mappings")
    op.drop_index("ix_external_id_mappings_market_id", table_name="external_id_mappings")
    op.drop_table("external_id_mappings")
    op.drop_index("ix_import_cursors_resource", table_name="import_cursors")
    op.drop_index("ix_import_cursors_provider", table_name="import_cursors")
    op.drop_index("ix_import_cursors_market_id", table_name="import_cursors")
    op.drop_table("import_cursors")
    op.drop_index("ix_import_runs_status", table_name="import_runs")
    op.drop_index("ix_import_runs_mode", table_name="import_runs")
    op.drop_index("ix_import_runs_provider", table_name="import_runs")
    op.drop_index("ix_import_runs_market_id", table_name="import_runs")
    op.drop_table("import_runs")
    op.drop_index("ix_customer_identities_normalized_value", table_name="customer_identities")
    op.drop_index("ix_customer_identities_identity_type", table_name="customer_identities")
    op.drop_index("ix_customer_identities_provider", table_name="customer_identities")
    op.drop_index("ix_customer_identities_customer_id", table_name="customer_identities")
    op.drop_index("ix_customer_identities_market_id", table_name="customer_identities")
    op.drop_table("customer_identities")
