"""add community forums (discussion topics + comments)

Revision ID: 20260607_0039
Revises: 20260607_0038
Create Date: 2026-06-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260607_0039"
down_revision: str | None = "20260607_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discussion_topics",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False, server_default="General"),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("author", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("reply_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discussion_topics_market_id", "discussion_topics", ["market_id"])
    op.create_index("ix_discussion_topics_category", "discussion_topics", ["category"])
    op.create_index("ix_discussion_topics_status", "discussion_topics", ["status"])
    op.create_index("ix_discussion_topics_pinned", "discussion_topics", ["pinned"])

    op.create_table(
        "discussion_comments",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("topic_id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("author", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["topic_id"], ["discussion_topics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discussion_comments_topic_id", "discussion_comments", ["topic_id"])
    op.create_index("ix_discussion_comments_market_id", "discussion_comments", ["market_id"])


def downgrade() -> None:
    op.drop_index("ix_discussion_comments_market_id", table_name="discussion_comments")
    op.drop_index("ix_discussion_comments_topic_id", table_name="discussion_comments")
    op.drop_table("discussion_comments")
    op.drop_index("ix_discussion_topics_pinned", table_name="discussion_topics")
    op.drop_index("ix_discussion_topics_status", table_name="discussion_topics")
    op.drop_index("ix_discussion_topics_category", table_name="discussion_topics")
    op.drop_index("ix_discussion_topics_market_id", table_name="discussion_topics")
    op.drop_table("discussion_topics")
