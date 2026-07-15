"""add per-user password hashes

Revision ID: 20260529_0005
Revises: 20260529_0004
Create Date: 2026-05-29
"""

from collections.abc import Sequence
import base64
import hashlib
from secrets import token_bytes

from alembic import op
import sqlalchemy as sa

revision: str = "20260529_0005"
down_revision: str | None = "20260529_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _hash_password(password: str) -> str:
    iterations = 210_000
    salt = token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_part = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    digest_part = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${iterations}${salt_part}${digest_part}"


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255)))
    op.add_column(
        "users",
        sa.Column(
            "password_reset_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True)))

    users = sa.table(
        "users",
        sa.column("id", sa.String(length=64)),
        sa.column("password_hash", sa.String(length=255)),
        sa.column("password_reset_required", sa.Boolean()),
    )
    connection = op.get_bind()
    for row in connection.execute(sa.select(users.c.id)):
        connection.execute(
            users.update()
            .where(users.c.id == row.id)
            .values(password_hash=_hash_password("omni-demo"), password_reset_required=False)
        )


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "password_reset_required")
    op.drop_column("users", "password_hash")
