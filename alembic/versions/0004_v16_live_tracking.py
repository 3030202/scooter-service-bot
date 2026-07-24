"""live repair tracking and photo journal

Revision ID: 0004_v16_live_tracking
Revises: 0003_v13_commercial_layer
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_v16_live_tracking"
down_revision = "0003_v13_commercial_layer"
branch_labels = None
depends_on = None

repair_stage_enum = sa.Enum("received", "diagnostics", "parts_ordering", "assembly", "testing", "ready", name="repairstage")


def upgrade() -> None:
    repair_stage_enum.create(op.get_bind(), checkfirst=True)
    repair_stage_col = sa.Enum(name="repairstage", create_type=False)

    op.add_column("tickets", sa.Column("repair_stage", repair_stage_col, server_default="received", nullable=False))
    op.add_column("tickets", sa.Column("pickup_method", sa.String(50), server_default="self_pickup", nullable=True))
    op.create_index("ix_tickets_repair_stage", "tickets", ["repair_stage"])

    op.create_table(
        "repair_journal_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("stage", repair_stage_col, server_default="received", nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("photo_file_id", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_repair_journal_entries_ticket_id", "repair_journal_entries", ["ticket_id"])
    op.create_index("ix_repair_journal_entries_stage", "repair_journal_entries", ["stage"])


def downgrade() -> None:
    op.drop_table("repair_journal_entries")
    op.drop_index("ix_tickets_repair_stage", table_name="tickets")
    op.drop_column("tickets", "pickup_method")
    op.drop_column("tickets", "repair_stage")
    repair_stage_enum.drop(op.get_bind(), checkfirst=True)
