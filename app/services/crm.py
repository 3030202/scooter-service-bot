from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import desc, func, select

from app.db.models import ClientProfile, RetentionReminder, Ticket, TicketStatus, User


async def get_or_create_profile(session, user: User) -> ClientProfile:
    profile = await session.scalar(select(ClientProfile).where(ClientProfile.user_id == user.id))
    if profile:
        return profile
    profile = ClientProfile(user_id=user.id, loyalty_tag="new")
    session.add(profile)
    await session.flush()
    return profile


async def update_profile_after_ticket_done(session, ticket: Ticket) -> ClientProfile | None:
    user = await session.get(User, ticket.client_id)
    if not user:
        return None
    profile = await get_or_create_profile(session, user)
    profile.repairs_count = (profile.repairs_count or 0) + 1
    if ticket.final_price:
        profile.total_spent = Decimal(str(profile.total_spent or 0)) + Decimal(str(ticket.final_price))
    profile.last_issue_summary = ticket.ai_fault or ticket.description
    if profile.repairs_count >= 3:
        profile.loyalty_tag = "repeat"
    elif profile.total_spent and Decimal(str(profile.total_spent)) >= Decimal("5000"):
        profile.loyalty_tag = "high_value"
    else:
        profile.loyalty_tag = "active"
    await session.flush()
    return profile


async def create_retention_after_done(session, ticket: Ticket) -> RetentionReminder:
    client = await session.get(User, ticket.client_id)
    message = f"Плановое ТО после ремонта по заявке #{ticket.id}: предложить бесплатную быструю проверку и сезонное обслуживание."
    reminder = RetentionReminder(
        client_id=ticket.client_id,
        ticket_id=ticket.id,
        kind="post_repair_checkup",
        due_at=datetime.now(timezone.utc) + timedelta(days=30),
        message=message,
    )
    session.add(reminder)
    await session.flush()
    return reminder


async def client_summary(session, user: User) -> str:
    profile = await get_or_create_profile(session, user)
    tickets_count = await session.scalar(select(func.count(Ticket.id)).where(Ticket.client_id == user.id))
    last_tickets = (await session.scalars(
        select(Ticket).where(Ticket.client_id == user.id).order_by(desc(Ticket.created_at)).limit(3)
    )).all()
    lines = [
        f"👤 Клиент: {user.full_name or 'без имени'}",
        f"Username: @{user.username}" if user.username else "Username: нет",
        f"Телефон: {user.phone or 'не указан'}",
        f"Тег: {profile.loyalty_tag or 'new'}",
        f"Ремонтов: {profile.repairs_count or 0}",
        f"Всего заявок: {tickets_count or 0}",
        f"Сумма ремонтов: {profile.total_spent or 0}",
    ]
    if profile.last_issue_summary:
        lines.extend(["", f"Последняя проблема: {profile.last_issue_summary}"])
    if last_tickets:
        lines.extend(["", "Последние заявки:"])
        for ticket in last_tickets:
            lines.append(f"• #{ticket.id} — {ticket.status.value}")
    return "\n".join(lines)


async def due_retention_items(session, limit: int = 10) -> list[RetentionReminder]:
    return (await session.scalars(
        select(RetentionReminder)
        .where(RetentionReminder.is_sent == False, RetentionReminder.due_at <= datetime.now(timezone.utc))
        .order_by(RetentionReminder.due_at)
        .limit(limit)
    )).all()
