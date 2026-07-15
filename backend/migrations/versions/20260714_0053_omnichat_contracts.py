"""add first-class Omnichat contracts and ticket versions

Revision ID: 20260714_0053
Revises: 20260714_0052
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260714_0053"
down_revision: str | None = "20260714_0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.add_column(
            sa.Column("version", sa.Integer(), nullable=False, server_default="1")
        )

    op.create_table(
        "conversation_topics",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="100"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_id", "name", name="uq_conversation_topic_market_name"
        ),
    )
    op.create_index("ix_conversation_topics_market_id", "conversation_topics", ["market_id"])
    op.create_index("ix_conversation_topics_active", "conversation_topics", ["active"])

    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="normal"),
        sa.Column("topic_id", sa.String(length=64)),
        sa.Column("assignee_id", sa.String(length=64)),
        sa.Column("assigned_group_id", sa.String(length=64)),
        sa.Column("source_account_id", sa.String(length=160)),
        sa.Column("external_id", sa.String(length=255)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("reopened_at", sa.DateTime(timezone=True)),
        sa.Column("conversation_metadata", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["topic_id"], ["conversation_topics.id"]),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["assigned_group_id"], ["support_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_id", "public_id", name="uq_chat_conversation_market_public_id"
        ),
        sa.UniqueConstraint(
            "market_id",
            "channel",
            "external_id",
            name="uq_chat_conversation_market_channel_external_id",
        ),
    )
    for column in (
        "market_id",
        "public_id",
        "case_id",
        "customer_id",
        "channel",
        "status",
        "priority",
        "topic_id",
        "assignee_id",
        "assigned_group_id",
        "source_account_id",
        "external_id",
        "last_message_at",
    ):
        op.create_index(f"ix_chat_conversations_{column}", "chat_conversations", [column])
    op.create_index(
        "ix_chat_conversations_market_status_activity",
        "chat_conversations",
        ["market_id", "status", "last_message_at"],
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=False),
        sa.Column("sender_type", sa.String(length=32), nullable=False),
        sa.Column("sender_id", sa.String(length=64)),
        sa.Column("sender_name", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default="public"),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column(
            "delivery_state",
            sa.String(length=32),
            nullable=False,
            server_default="pending_provider",
        ),
        sa.Column("provider_message_id", sa.String(length=255)),
        sa.Column("idempotency_key", sa.String(length=180)),
        sa.Column("reply_to_id", sa.String(length=64)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("message_metadata", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"]),
        sa.ForeignKeyConstraint(["reply_to_id"], ["chat_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_id",
            "provider_message_id",
            name="uq_chat_message_market_provider_message_id",
        ),
        sa.UniqueConstraint(
            "conversation_id",
            "idempotency_key",
            name="uq_chat_message_conversation_idempotency_key",
        ),
    )
    for column in (
        "market_id",
        "conversation_id",
        "sender_type",
        "sender_id",
        "visibility",
        "delivery_state",
        "provider_message_id",
        "sent_at",
    ):
        op.create_index(f"ix_chat_messages_{column}", "chat_messages", [column])
    op.create_index(
        "ix_chat_messages_conversation_sent",
        "chat_messages",
        ["conversation_id", "sent_at", "id"],
    )

    op.create_table(
        "chat_participants",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=False),
        sa.Column("participant_type", sa.String(length=24), nullable=False),
        sa.Column("user_id", sa.String(length=64)),
        sa.Column("customer_id", sa.String(length=64)),
        sa.Column("display_name", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=40), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "participant_type",
            "user_id",
            "customer_id",
            name="uq_chat_participant_identity",
        ),
    )
    for column in ("market_id", "conversation_id", "participant_type", "user_id", "customer_id"):
        op.create_index(f"ix_chat_participants_{column}", "chat_participants", [column])

    op.create_table(
        "conversation_assignments",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=False),
        sa.Column("from_user_id", sa.String(length=64)),
        sa.Column("to_user_id", sa.String(length=64)),
        sa.Column("from_group_id", sa.String(length=64)),
        sa.Column("to_group_id", sa.String(length=64)),
        sa.Column("reason", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("routed_by", sa.String(length=180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("market_id", "conversation_id", "to_user_id", "to_group_id", "created_at"):
        op.create_index(f"ix_conversation_assignments_{column}", "conversation_assignments", [column])

    op.create_table(
        "conversation_views",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.String(length=64)),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("sort_by", sa.String(length=40), nullable=False, server_default="last_message_at"),
        sa.Column("sort_order", sa.String(length=8), nullable=False, server_default="desc"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_id", "owner_user_id", "name", name="uq_conversation_view_owner_name"
        ),
    )
    for column in ("market_id", "owner_user_id", "active"):
        op.create_index(f"ix_conversation_views_{column}", "conversation_views", [column])

    op.create_table(
        "message_receipts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("receipt_type", sa.String(length=24), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id", "user_id", "receipt_type", name="uq_message_receipt_user_type"
        ),
    )
    for column in (
        "market_id",
        "conversation_id",
        "message_id",
        "user_id",
        "receipt_type",
        "recorded_at",
    ):
        op.create_index(f"ix_message_receipts_{column}", "message_receipts", [column])

    op.create_table(
        "conversation_ticket_links",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("relationship", sa.String(length=32), nullable=False, server_default="linked"),
        sa.Column("created_by", sa.String(length=180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "ticket_id", name="uq_conversation_ticket_link"
        ),
    )
    for column in ("market_id", "conversation_id", "ticket_id"):
        op.create_index(f"ix_conversation_ticket_links_{column}", "conversation_ticket_links", [column])

    op.create_table(
        "conversation_attachments",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=False),
        sa.Column("message_id", sa.String(length=64)),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column(
            "content_type",
            sa.String(length=160),
            nullable=False,
            server_default="application/octet-stream",
        ),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_provider", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("scan_status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("lifecycle_status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("uploaded_by", sa.String(length=180), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "market_id",
        "conversation_id",
        "message_id",
        "scan_status",
        "lifecycle_status",
    ):
        op.create_index(f"ix_conversation_attachments_{column}", "conversation_attachments", [column])

    op.create_table(
        "feature_flags",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allowed_roles", sa.JSON(), nullable=False),
        sa.Column("allowed_user_ids", sa.JSON(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(length=180), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "key", name="uq_feature_flag_market_key"),
    )
    for column in ("market_id", "key", "enabled"):
        op.create_index(f"ix_feature_flags_{column}", "feature_flags", [column])


def downgrade() -> None:
    for table in (
        "feature_flags",
        "conversation_attachments",
        "conversation_ticket_links",
        "message_receipts",
        "conversation_views",
        "conversation_assignments",
        "chat_participants",
        "chat_messages",
        "chat_conversations",
        "conversation_topics",
    ):
        op.drop_table(table)
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_column("version")
