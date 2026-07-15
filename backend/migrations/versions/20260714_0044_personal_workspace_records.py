"""store personal tasks, ticket watches, and time entries on the server

Revision ID: 20260714_0044
Revises: 20260714_0043
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260714_0044"
down_revision: str | None = "20260714_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "personal_tasks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personal_tasks_market_id", "personal_tasks", ["market_id"])
    op.create_index("ix_personal_tasks_user_id", "personal_tasks", ["user_id"])
    op.create_index("ix_personal_tasks_completed", "personal_tasks", ["completed"])

    op.create_table(
        "ticket_watchers",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", "user_id", name="uq_ticket_watcher_ticket_user"),
    )
    op.create_index("ix_ticket_watchers_market_id", "ticket_watchers", ["market_id"])
    op.create_index("ix_ticket_watchers_ticket_id", "ticket_watchers", ["ticket_id"])
    op.create_index("ix_ticket_watchers_user_id", "ticket_watchers", ["user_id"])

    op.create_table(
        "ticket_time_entries",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("billable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_time_entries_market_id", "ticket_time_entries", ["market_id"])
    op.create_index("ix_ticket_time_entries_ticket_id", "ticket_time_entries", ["ticket_id"])
    op.create_index("ix_ticket_time_entries_user_id", "ticket_time_entries", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_ticket_time_entries_user_id", table_name="ticket_time_entries")
    op.drop_index("ix_ticket_time_entries_ticket_id", table_name="ticket_time_entries")
    op.drop_index("ix_ticket_time_entries_market_id", table_name="ticket_time_entries")
    op.drop_table("ticket_time_entries")
    op.drop_index("ix_ticket_watchers_user_id", table_name="ticket_watchers")
    op.drop_index("ix_ticket_watchers_ticket_id", table_name="ticket_watchers")
    op.drop_index("ix_ticket_watchers_market_id", table_name="ticket_watchers")
    op.drop_table("ticket_watchers")
    op.drop_index("ix_personal_tasks_completed", table_name="personal_tasks")
    op.drop_index("ix_personal_tasks_user_id", table_name="personal_tasks")
    op.drop_index("ix_personal_tasks_market_id", table_name="personal_tasks")
    op.drop_table("personal_tasks")
