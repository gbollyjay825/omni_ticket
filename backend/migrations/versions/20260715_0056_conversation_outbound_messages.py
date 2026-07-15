"""Allow durable outbound delivery for first-class chat conversations.

Revision ID: 20260715_0056
Revises: 20260714_0055
"""

from alembic import op
import sqlalchemy as sa


revision = "20260715_0056"
down_revision = "20260714_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("outbound_messages") as batch_op:
        batch_op.alter_column("ticket_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.add_column(sa.Column("conversation_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("chat_message_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_outbound_messages_conversation_id_chat_conversations",
            "chat_conversations",
            ["conversation_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_outbound_messages_chat_message_id_chat_messages",
            "chat_messages",
            ["chat_message_id"],
            ["id"],
        )
        batch_op.create_index("ix_outbound_messages_conversation_id", ["conversation_id"])
        batch_op.create_index("ix_outbound_messages_chat_message_id", ["chat_message_id"])
        batch_op.create_check_constraint(
            "ck_outbound_message_single_source",
            "(ticket_id IS NOT NULL AND conversation_id IS NULL) OR "
            "(ticket_id IS NULL AND conversation_id IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("outbound_messages") as batch_op:
        batch_op.drop_constraint("ck_outbound_message_single_source", type_="check")
        batch_op.drop_index("ix_outbound_messages_chat_message_id")
        batch_op.drop_index("ix_outbound_messages_conversation_id")
        batch_op.drop_constraint(
            "fk_outbound_messages_chat_message_id_chat_messages", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_outbound_messages_conversation_id_chat_conversations", type_="foreignkey"
        )
        batch_op.drop_column("chat_message_id")
        batch_op.drop_column("conversation_id")
        batch_op.alter_column("ticket_id", existing_type=sa.String(length=64), nullable=False)
