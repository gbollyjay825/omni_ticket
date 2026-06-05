"""add oidc identity linkage and login state

Revision ID: 20260604_0015
Revises: 20260604_0014
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260604_0015"
down_revision: str | None = "20260604_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("external_identity_provider", sa.String(length=80)))
    op.add_column("users", sa.Column("external_subject", sa.String(length=255)))
    op.add_column("users", sa.Column("external_last_login_at", sa.DateTime(timezone=True)))
    op.create_index("ix_users_external_subject", "users", ["external_subject"])
    op.create_table(
        "oidc_login_states",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("state_hash", sa.String(length=96), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("return_to", sa.String(length=500)),
        sa.Column("code_verifier", sa.String(length=160), nullable=False),
        sa.Column("nonce", sa.String(length=160), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index("ix_oidc_login_states_expires_at", "oidc_login_states", ["expires_at"])
    op.create_index("ix_oidc_login_states_market_id", "oidc_login_states", ["market_id"])
    op.create_index("ix_oidc_login_states_state_hash", "oidc_login_states", ["state_hash"])
    op.create_index("ix_oidc_login_states_used_at", "oidc_login_states", ["used_at"])


def downgrade() -> None:
    op.drop_index("ix_oidc_login_states_used_at", table_name="oidc_login_states")
    op.drop_index("ix_oidc_login_states_state_hash", table_name="oidc_login_states")
    op.drop_index("ix_oidc_login_states_market_id", table_name="oidc_login_states")
    op.drop_index("ix_oidc_login_states_expires_at", table_name="oidc_login_states")
    op.drop_table("oidc_login_states")
    op.drop_index("ix_users_external_subject", table_name="users")
    op.drop_column("users", "external_last_login_at")
    op.drop_column("users", "external_subject")
    op.drop_column("users", "external_identity_provider")
