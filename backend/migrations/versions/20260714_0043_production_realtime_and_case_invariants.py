"""enforce active case ownership and add durable realtime events

Revision ID: 20260714_0043
Revises: 20260615_0042
Create Date: 2026-07-14
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "20260714_0043"
down_revision: str | None = "20260615_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill_case_ownership() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    open_cases = bind.execute(
        sa.text(
            """
            SELECT id, market_id, customer_id
            FROM cases
            WHERE status = 'open'
            ORDER BY created_at ASC, id ASC
            """
        )
    ).mappings()
    active_by_customer: dict[tuple[str, str], str] = {}
    for item in open_cases:
        key = (str(item["market_id"]), str(item["customer_id"]))
        keeper_id = active_by_customer.get(key)
        if keeper_id is None:
            active_by_customer[key] = str(item["id"])
            continue
        duplicate_id = str(item["id"])
        bind.execute(
            sa.text("UPDATE tickets SET case_id = :keeper WHERE case_id = :duplicate"),
            {"keeper": keeper_id, "duplicate": duplicate_id},
        )
        bind.execute(
            sa.text(
                """
                UPDATE cases
                SET status = 'closed',
                    summary = CASE
                        WHEN summary = '' THEN :note
                        ELSE summary || :suffix
                    END,
                    updated_at = :now
                WHERE id = :duplicate
                """
            ),
            {
                "duplicate": duplicate_id,
                "note": f"Consolidated into active case {keeper_id} during migration.",
                "suffix": f"\nConsolidated into active case {keeper_id} during migration.",
                "now": now,
            },
        )

    unlinked = bind.execute(
        sa.text(
            """
            SELECT id, market_id, customer_id, subject, description, priority, status
            FROM tickets
            WHERE case_id IS NULL
            ORDER BY created_at ASC, id ASC
            """
        )
    ).mappings()
    tickets_by_customer: dict[tuple[str, str], list[dict]] = {}
    for ticket in unlinked:
        key = (str(ticket["market_id"]), str(ticket["customer_id"]))
        tickets_by_customer.setdefault(key, []).append(dict(ticket))

    for (market_id, customer_id), tickets in tickets_by_customer.items():
        case_id = active_by_customer.get((market_id, customer_id))
        if case_id is None:
            has_active_ticket = any(ticket["status"] not in {"solved", "closed"} for ticket in tickets)
            case_id = f"case_migration_{uuid4().hex}"
            first = tickets[0]
            bind.execute(
                sa.text(
                    """
                    INSERT INTO cases (
                        id, market_id, public_id, customer_id, title, status,
                        priority, summary, opened_by, created_at, updated_at
                    ) VALUES (
                        :id, :market_id, :public_id, :customer_id, :title, :status,
                        :priority, :summary, :opened_by, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": case_id,
                    "market_id": market_id,
                    "public_id": f"CASE-MIG-{uuid4().hex[:12].upper()}",
                    "customer_id": customer_id,
                    "title": str(first["subject"]),
                    "status": "open" if has_active_ticket else "closed",
                    "priority": str(first["priority"]),
                    "summary": str(first["description"] or ""),
                    "opened_by": "migration",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            if has_active_ticket:
                active_by_customer[(market_id, customer_id)] = case_id
        ticket_ids = [str(ticket["id"]) for ticket in tickets]
        bind.execute(
            sa.text("UPDATE tickets SET case_id = :case_id WHERE id IN :ticket_ids").bindparams(
                sa.bindparam("ticket_ids", expanding=True)
            ),
            {"case_id": case_id, "ticket_ids": ticket_ids},
        )


def upgrade() -> None:
    _backfill_case_ownership()
    open_case = sa.text("status = 'open'")
    op.create_index(
        "uq_cases_active_customer_market",
        "cases",
        ["market_id", "customer_id"],
        unique=True,
        postgresql_where=open_case,
        sqlite_where=open_case,
    )
    op.create_table(
        "realtime_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False, server_default="wakanow"),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_realtime_events_organization_id", "realtime_events", ["organization_id"])
    op.create_index("ix_realtime_events_market_id", "realtime_events", ["market_id"])
    op.create_index("ix_realtime_events_type", "realtime_events", ["type"])
    op.create_index("ix_realtime_events_aggregate_type", "realtime_events", ["aggregate_type"])
    op.create_index("ix_realtime_events_aggregate_id", "realtime_events", ["aggregate_id"])
    op.create_index("ix_realtime_events_created_at", "realtime_events", ["created_at"])
    op.create_index(
        "ix_realtime_events_market_cursor",
        "realtime_events",
        ["market_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_realtime_events_market_cursor", table_name="realtime_events")
    op.drop_index("ix_realtime_events_created_at", table_name="realtime_events")
    op.drop_index("ix_realtime_events_aggregate_id", table_name="realtime_events")
    op.drop_index("ix_realtime_events_aggregate_type", table_name="realtime_events")
    op.drop_index("ix_realtime_events_type", table_name="realtime_events")
    op.drop_index("ix_realtime_events_market_id", table_name="realtime_events")
    op.drop_index("ix_realtime_events_organization_id", table_name="realtime_events")
    op.drop_table("realtime_events")
    op.drop_index("uq_cases_active_customer_market", table_name="cases")
