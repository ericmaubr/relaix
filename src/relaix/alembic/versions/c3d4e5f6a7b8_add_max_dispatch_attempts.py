"""add max_dispatch_attempts to webhook_source

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-01 00:00:00.000001

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "webhook_source",
        sa.Column(
            "max_dispatch_attempts", sa.Integer(), server_default="3", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("webhook_source", "max_dispatch_attempts")
