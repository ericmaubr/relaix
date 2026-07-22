"""initial schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-07-22 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "webhook_source",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), server_default="webhook_site", nullable=False),
        sa.Column("api_url", sa.String(), nullable=False),
        sa.Column("api_token", sa.String(), nullable=True),
        sa.Column("channel_id", sa.String(), nullable=True),
        sa.Column(
            "polling_interval_seconds",
            sa.Integer(),
            server_default="300",
            nullable=False,
        ),
        sa.Column("last_processed_cursor", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "webhook_polling_log",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("executed_at", sa.String(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("new_events_found", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["webhook_source.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_webhook_polling_log_source",
        "webhook_polling_log",
        ["source_id"],
        unique=False,
    )

    op.create_table(
        "webhook_event",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("received_at", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["webhook_source.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_webhook_event_source", "webhook_event", ["source_id"], unique=False
    )
    op.create_index(
        "idx_webhook_event_status", "webhook_event", ["status"], unique=False
    )
    op.create_index(
        "idx_webhook_event_source_external_id",
        "webhook_event",
        ["source_id", "external_id"],
        unique=True,
    )

    op.create_table(
        "webhook_rule",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("action_url", sa.String(), nullable=False),
        sa.Column("action_token", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["webhook_source.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_webhook_rule_source", "webhook_rule", ["source_id"], unique=False
    )

    op.create_table(
        "webhook_rule_condition",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("group_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("field_path", sa.String(), nullable=False),
        sa.Column("operator", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["webhook_rule.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_webhook_rule_condition_rule",
        "webhook_rule_condition",
        ["rule_id"],
        unique=False,
    )

    op.create_table(
        "webhook_rule_execution",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("response_http_status", sa.Integer(), nullable=True),
        sa.Column("response_detail", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["webhook_event.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["webhook_rule.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_webhook_rule_execution_event",
        "webhook_rule_execution",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        "idx_webhook_rule_execution_rule",
        "webhook_rule_execution",
        ["rule_id"],
        unique=False,
    )
    op.create_index(
        "idx_webhook_rule_execution_status",
        "webhook_rule_execution",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("webhook_rule_execution")
    op.drop_table("webhook_rule_condition")
    op.drop_table("webhook_rule")
    op.drop_table("webhook_event")
    op.drop_table("webhook_polling_log")
    op.drop_table("webhook_source")
