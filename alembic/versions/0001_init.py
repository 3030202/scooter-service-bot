"""init tables

Revision ID: 0001_init
Revises:
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    user_role = sa.Enum("CLIENT", "MASTER", "ADMIN", name="userrole")
    ticket_status = sa.Enum("DRAFT", "WAITING_PHOTOS", "AI_ANALYSIS", "NEW", "ACCEPTED", "IN_PROGRESS", "WAITING_APPROVAL", "DONE", "CANCELLED", name="ticketstatus")
    media_type = sa.Enum("PHOTO", "VOICE", name="mediatype")
    slot_status = sa.Enum("RESERVED", "BUSY", "DONE", "CANCELLED", name="calendarslotstatus")
    user_role.create(op.get_bind(), checkfirst=True)
    ticket_status.create(op.get_bind(), checkfirst=True)
    media_type.create(op.get_bind(), checkfirst=True)
    slot_status.create(op.get_bind(), checkfirst=True)

    user_role_col = sa.Enum(name="userrole", create_type=False)
    ticket_status_col = sa.Enum(name="ticketstatus", create_type=False)
    media_type_col = sa.Enum(name="mediatype", create_type=False)
    slot_status_col = sa.Enum(name="calendarslotstatus", create_type=False)

    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255)),
        sa.Column("full_name", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("role", user_role_col, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table("tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("master_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("status", ticket_status_col, nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("transcript", sa.Text()),
        sa.Column("ai_fault", sa.Text()),
        sa.Column("ai_price_min", sa.Numeric(10, 2)),
        sa.Column("ai_price_max", sa.Numeric(10, 2)),
        sa.Column("ai_eta", sa.String(255)),
        sa.Column("ai_raw_json", sa.Text()),
        sa.Column("final_price", sa.Numeric(10, 2)),
        sa.Column("final_eta", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_tickets_client_id", "tickets", ["client_id"])
    op.create_index("ix_tickets_status", "tickets", ["status"])

    op.create_table("media",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("type", media_type_col, nullable=False),
        sa.Column("telegram_file_id", sa.String(512), nullable=False),
        sa.Column("telegram_file_unique_id", sa.String(512)),
        sa.Column("local_path", sa.String(1024)),
        sa.Column("mime_type", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_media_ticket_id", "media", ["ticket_id"])

    op.create_table("calendar_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("master_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", slot_status_col, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_calendar_slots_ticket_id", "calendar_slots", ["ticket_id"])
    op.create_index("ix_calendar_slots_starts_at", "calendar_slots", ["starts_at"])
    op.create_index("ix_calendar_slots_ends_at", "calendar_slots", ["ends_at"])
    op.create_index("ix_calendar_slots_status", "calendar_slots", ["status"])


def downgrade() -> None:
    op.drop_table("calendar_slots")
    op.drop_table("media")
    op.drop_table("tickets")
    op.drop_table("users")
    sa.Enum(name="calendarslotstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="mediatype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ticketstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
