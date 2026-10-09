"""add dispatch_timeout_seconds to webhook_rule

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-09 00:00:00.000001

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "webhook_rule",
        sa.Column(
            "dispatch_timeout_seconds",
            sa.Integer(),
            server_default="30",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("webhook_rule", "dispatch_timeout_seconds")
