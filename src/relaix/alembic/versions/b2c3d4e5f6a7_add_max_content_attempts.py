"""add max_content_attempts to webhook_source

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-22 00:00:00.000001

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "webhook_source",
        sa.Column(
            "max_content_attempts", sa.Integer(), server_default="3", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("webhook_source", "max_content_attempts")
