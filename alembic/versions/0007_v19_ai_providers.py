"""ai providers and dynamic models auto discovery

Revision ID: 0007_v19_ai_providers
Revises: 0006_v18_workload_calendar
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_v19_ai_providers"
down_revision = "0006_v18_workload_calendar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("api_key", sa.String(512), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_ai_providers_is_active", "ai_providers", ["is_active"])
    op.create_index("ix_ai_providers_is_default", "ai_providers", ["is_default"])

    op.create_table(
        "ai_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("ai_providers.id"), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_ai_models_provider_id", "ai_models", ["provider_id"])
    op.create_index("ix_ai_models_is_active", "ai_models", ["is_active"])


def downgrade() -> None:
    op.drop_table("ai_models")
    op.drop_table("ai_providers")
