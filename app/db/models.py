import enum
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    CLIENT = "client"
    MASTER = "master"
    ADMIN = "admin"


class TicketStatus(str, enum.Enum):
    DRAFT = "draft"
    WAITING_PHOTOS = "waiting_photos"
    AI_ANALYSIS = "ai_analysis"
    DIAGNOSED = "diagnosed"
    NEW = "new"
    ACCEPTED = "accepted"  # legacy compatibility
    ASSIGNED = "assigned"
    WAITING_APPROVAL = "waiting_approval"  # legacy compatibility
    PRICE_OFFERED = "price_offered"
    CLIENT_APPROVED = "client_approved"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class MediaType(str, enum.Enum):
    PHOTO = "photo"
    VOICE = "voice"


class CalendarSlotStatus(str, enum.Enum):
    RESERVED = "reserved"
    BUSY = "busy"
    DONE = "done"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.CLIENT)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="client", foreign_keys="Ticket.client_id")
    profile: Mapped["ClientProfile | None"] = relationship(back_populates="user", cascade="all, delete-orphan")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    master_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.DRAFT, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)

    ai_fault: Mapped[str | None] = mapped_column(Text)
    ai_price_min: Mapped[float | None] = mapped_column(Numeric(10, 2))
    ai_price_max: Mapped[float | None] = mapped_column(Numeric(10, 2))
    ai_eta: Mapped[str | None] = mapped_column(String(255))
    ai_raw_json: Mapped[str | None] = mapped_column(Text)

    final_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    final_eta: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    client: Mapped["User"] = relationship(foreign_keys=[client_id], back_populates="tickets")
    media: Mapped[list["Media"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")
    calendar_slots: Mapped[list["CalendarSlot"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")
    service_items: Mapped[list["TicketServiceItem"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    type: Mapped[MediaType] = mapped_column(Enum(MediaType))
    telegram_file_id: Mapped[str] = mapped_column(String(512))
    telegram_file_unique_id: Mapped[str | None] = mapped_column(String(512))
    local_path: Mapped[str | None] = mapped_column(String(1024))
    mime_type: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    ticket: Mapped["Ticket"] = relationship(back_populates="media")


class CalendarSlot(Base):
    __tablename__ = "calendar_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    master_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[CalendarSlotStatus] = mapped_column(Enum(CalendarSlotStatus), default=CalendarSlotStatus.RESERVED, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    ticket: Mapped["Ticket"] = relationship(back_populates="calendar_slots")


class ClientProfile(Base):
    __tablename__ = "client_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(120))
    vehicle_model: Mapped[str | None] = mapped_column(String(255))
    last_issue_summary: Mapped[str | None] = mapped_column(Text)
    repairs_count: Mapped[int] = mapped_column(Integer, default=0)
    total_spent: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    loyalty_tag: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="profile")


class ServiceCatalogItem(Base):
    __tablename__ = "service_catalog_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(120), index=True)
    base_price: Mapped[float] = mapped_column(Numeric(10, 2))
    min_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    max_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    default_eta: Mapped[str | None] = mapped_column(String(255))
    keywords: Mapped[str | None] = mapped_column(Text)
    checklist: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TicketServiceItem(Base):
    __tablename__ = "ticket_service_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    catalog_item_id: Mapped[int | None] = mapped_column(ForeignKey("service_catalog_items.id"))
    title: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    ticket: Mapped["Ticket"] = relationship(back_populates="service_items")
    catalog_item: Mapped["ServiceCatalogItem | None"] = relationship()


class RetentionReminder(Base):
    __tablename__ = "retention_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id"))
    kind: Mapped[str] = mapped_column(String(80), index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    message: Mapped[str] = mapped_column(Text)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
