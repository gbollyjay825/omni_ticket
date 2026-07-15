"""switch Nigeria support identity to jimb mailbox

Revision ID: 20260604_0020
Revises: 20260604_0019
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260604_0020"
down_revision: str | None = "20260604_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE markets
        SET support_email = 'jimb@wakanow.com'
        WHERE id = 'market-ng' AND support_email = 'omni@wakanow.com'
        """
    )
    op.execute(
        """
        UPDATE channels
        SET handle = 'jimb@wakanow.com'
        WHERE id = 'channel-email' AND handle = 'omni@wakanow.com'
        """
    )
    op.execute(
        """
        UPDATE connector_accounts
        SET account_identifier = 'jimb@wakanow.com'
        WHERE id = 'connector-ng-email' AND account_identifier = 'omni@wakanow.com'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE connector_accounts
        SET account_identifier = 'omni@wakanow.com'
        WHERE id = 'connector-ng-email' AND account_identifier = 'jimb@wakanow.com'
        """
    )
    op.execute(
        """
        UPDATE channels
        SET handle = 'omni@wakanow.com'
        WHERE id = 'channel-email' AND handle = 'jimb@wakanow.com'
        """
    )
    op.execute(
        """
        UPDATE markets
        SET support_email = 'omni@wakanow.com'
        WHERE id = 'market-ng' AND support_email = 'jimb@wakanow.com'
        """
    )
