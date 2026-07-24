"""telegram payments and transaction log

Revision ID: 0005_v17_telegram_payments
Revises: 0004_v16_live_tracking
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

revision = "0005_v17_telegram_payments"
down_revision = "0004_v16_live_tracking"
branch_labels = None
depends_on = None

payment_status_enum = PGEnum("unpaid", "prepaid", "paid", "refunded", name="paymentstatus", create_type=False)


def upgrade() -> None:
    payment_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column("tickets", sa.Column("payment_status", payment_status_enum, server_default="unpaid", nullable=False))
    op.add_column("tickets", sa.Column("payment_id", sa.String(255), nullable=True))
    op.create_index("ix_tickets_payment_status", "tickets", ["payment_status"])

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(10), server_default="RUB", nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(255), nullable=False),
        sa.Column("provider_payment_charge_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_payment_transactions_ticket_id", "payment_transactions", ["ticket_id"])


def downgrade() -> None:
    op.drop_table("payment_transactions")
    op.drop_index("ix_tickets_payment_status", table_name="tickets")
    op.drop_column("tickets", "payment_id")
    op.drop_column("tickets", "payment_status")
    payment_status_enum.drop(op.get_bind(), checkfirst=True)
