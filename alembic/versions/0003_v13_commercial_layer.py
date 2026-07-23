"""commercial CRM catalog retention layer

Revision ID: 0003_v13_commercial_layer
Revises: 0002_v11_ticket_workflow
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_v13_commercial_layer"
down_revision = "0002_v11_ticket_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_type", sa.String(120)),
        sa.Column("vehicle_model", sa.String(255)),
        sa.Column("last_issue_summary", sa.Text()),
        sa.Column("repairs_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_spent", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("loyalty_tag", sa.String(80)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_client_profiles_user_id", "client_profiles", ["user_id"], unique=True)

    op.create_table(
        "service_catalog_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("base_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("min_price", sa.Numeric(10, 2)),
        sa.Column("max_price", sa.Numeric(10, 2)),
        sa.Column("default_eta", sa.String(255)),
        sa.Column("keywords", sa.Text()),
        sa.Column("checklist", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_service_catalog_items_code", "service_catalog_items", ["code"], unique=True)
    op.create_index("ix_service_catalog_items_category", "service_catalog_items", ["category"])
    op.create_index("ix_service_catalog_items_is_active", "service_catalog_items", ["is_active"])

    op.create_table(
        "ticket_service_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("catalog_item_id", sa.Integer(), sa.ForeignKey("service_catalog_items.id")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("qty", sa.Integer(), server_default="1", nullable=False),
        sa.Column("source", sa.String(50), server_default="manual", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_ticket_service_items_ticket_id", "ticket_service_items", ["ticket_id"])

    op.create_table(
        "retention_reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id")),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_sent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_retention_reminders_client_id", "retention_reminders", ["client_id"])
    op.create_index("ix_retention_reminders_kind", "retention_reminders", ["kind"])
    op.create_index("ix_retention_reminders_due_at", "retention_reminders", ["due_at"])
    op.create_index("ix_retention_reminders_is_sent", "retention_reminders", ["is_sent"])


def downgrade() -> None:
    op.drop_table("retention_reminders")
    op.drop_table("ticket_service_items")
    op.drop_table("service_catalog_items")
    op.drop_table("client_profiles")
