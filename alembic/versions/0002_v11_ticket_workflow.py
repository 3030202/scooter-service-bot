"""extend ticket workflow statuses

Revision ID: 0002_v11_ticket_workflow
Revises: 0001_init
Create Date: 2026-07-05
"""
from alembic import op

revision = "0002_v11_ticket_workflow"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for value in ("DIAGNOSED", "PRICE_OFFERED", "CLIENT_APPROVED", "ASSIGNED"):
        op.execute(f"ALTER TYPE ticketstatus ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL cannot safely remove enum values without rebuilding the type.
    pass
