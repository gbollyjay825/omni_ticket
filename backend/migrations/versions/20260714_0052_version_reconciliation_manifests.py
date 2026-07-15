"""version import reconciliation manifests

Revision ID: 20260714_0052
Revises: 20260714_0051
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260714_0052"
down_revision: str | None = "20260714_0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("import_reconciliations") as batch_op:
        batch_op.drop_constraint(
            "uq_import_reconciliation_market_provider_entity",
            type_="unique",
        )


def downgrade() -> None:
    with op.batch_alter_table("import_reconciliations") as batch_op:
        batch_op.create_unique_constraint(
            "uq_import_reconciliation_market_provider_entity",
            ["market_id", "provider", "entity_type"],
        )
