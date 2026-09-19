"""Initial schema: usage logs, budgets, reservations, alerts

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-09-19 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. LLM Usage Logs
    op.create_table(
        "llm_usage_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=256), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=False, server_default="0.0"),
        sa.Column("actual_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="SUCCESS"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_llm_usage_logs_request_id", "llm_usage_logs", ["request_id"])
    op.create_index("ix_llm_usage_logs_user_id", "llm_usage_logs", ["user_id"])
    op.create_index("ix_llm_usage_logs_endpoint", "llm_usage_logs", ["endpoint"])
    op.create_index("ix_llm_usage_logs_provider", "llm_usage_logs", ["provider"])
    op.create_index("ix_llm_usage_logs_model", "llm_usage_logs", ["model"])
    op.create_index("ix_llm_usage_logs_timestamp", "llm_usage_logs", ["timestamp"])
    op.create_index("ix_llm_usage_logs_status", "llm_usage_logs", ["status"])
    op.create_index("ix_usage_user_timestamp", "llm_usage_logs", ["user_id", "timestamp"])
    op.create_index("ix_usage_model_timestamp", "llm_usage_logs", ["model", "timestamp"])
    op.create_index("ix_usage_endpoint_timestamp", "llm_usage_logs", ["endpoint", "timestamp"])

    # 2. Budget Configs
    op.create_table(
        "budget_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("daily_budget", sa.Numeric(12, 4), nullable=True),
        sa.Column("weekly_budget", sa.Numeric(12, 4), nullable=True),
        sa.Column("monthly_budget", sa.Numeric(12, 4), nullable=True),
        sa.Column("alert_thresholds", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_budget_configs_scope", "budget_configs", ["scope"], unique=True)

    # 3. Budget Reservations
    op.create_table(
        "budget_reservations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_budget_reservations_scope", "budget_reservations", ["scope"])
    op.create_index("ix_budget_reservations_request_id", "budget_reservations", ["request_id"])
    op.create_index("ix_budget_reservations_status", "budget_reservations", ["status"])
    op.create_index("ix_budget_reservations_expires_at", "budget_reservations", ["expires_at"])
    op.create_index("ix_res_scope_status_expires", "budget_reservations", ["scope", "status", "expires_at"])

    # 4. Alert Events
    op.create_table(
        "alert_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("period_type", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("threshold", sa.Numeric(5, 2), nullable=False),
        sa.Column("spent_amount", sa.Numeric(12, 6), nullable=False),
        sa.Column("budget_amount", sa.Numeric(12, 4), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="console"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DELIVERED"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "scope", "period_type", "period_start", "threshold",
            name="uq_alert_scope_period_threshold"
        ),
    )
    op.create_index("ix_alert_events_scope", "alert_events", ["scope"])
    op.create_index("ix_alerts_scope_created", "alert_events", ["scope", "created_at"])


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_table("budget_reservations")
    op.drop_table("budget_configs")
    op.drop_table("llm_usage_logs")
