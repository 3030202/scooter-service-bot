"""workload calendar and slot notes

Revision ID: 0007_v18_workload_calendar
Revises: 0006_add_commander_role
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_v18_workload_calendar"
down_revision = "0006_add_commander_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("calendar_slots", "ticket_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("calendar_slots", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("calendar_slots", "note")
    op.alter_column("calendar_slots", "ticket_id", existing_type=sa.Integer(), nullable=False)
