"""add commander role to userrole enum

Revision ID: 0006_add_commander_role
Revises: 0005_v17_telegram_payments
Create Date: 2026-07-24
"""
from alembic import op

revision = "0006_add_commander_role"
down_revision = "0005_v17_telegram_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'commander'")


def downgrade() -> None:
    pass
