from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CalendarSlot, CalendarSlotStatus


def service_tz() -> ZoneInfo:
    return ZoneInfo(settings.service_timezone)


def to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def to_service_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(service_tz())


def format_slot(slot: CalendarSlot | None) -> str:
    if not slot:
        return "слот подберет приемщик"
    starts = to_service_time(slot.starts_at)
    ends = to_service_time(slot.ends_at)
    return f"{starts:%d.%m.%Y %H:%M}–{ends:%H:%M} {settings.service_timezone}"


def _round_up_to_next_hour(now: datetime) -> datetime:
    rounded = now.replace(minute=0, second=0, microsecond=0)
    if rounded <= now:
        rounded += timedelta(hours=1)
    return rounded


def _business_candidates() -> list[tuple[datetime, datetime]]:
    tz = service_tz()
    now = datetime.now(tz)
    cursor = _round_up_to_next_hour(now)
    duration = timedelta(minutes=settings.slot_duration_minutes)
    slots: list[tuple[datetime, datetime]] = []

    for day_offset in range(settings.slot_search_days + 1):
        day = (now + timedelta(days=day_offset)).date()
        if day.weekday() not in settings.workday_numbers:
            continue

        day_start = datetime.combine(day, time(settings.workday_start_hour, 0), tz)
        day_end = datetime.combine(day, time(settings.workday_end_hour, 0), tz)
        candidate = max(cursor, day_start)
        candidate = candidate.replace(minute=0, second=0, microsecond=0)

        while candidate + duration <= day_end:
            if candidate > now:
                slots.append((to_utc_naive(candidate), to_utc_naive(candidate + duration)))
            candidate += timedelta(minutes=30)

    return slots


async def is_slot_busy(session: AsyncSession, starts_at: datetime, ends_at: datetime, master_id: int | None = None) -> bool:
    query = select(CalendarSlot).where(
        CalendarSlot.starts_at < ends_at,
        CalendarSlot.ends_at > starts_at,
        CalendarSlot.status.in_([CalendarSlotStatus.RESERVED, CalendarSlotStatus.BUSY]),
    )
    if master_id is not None:
        query = query.where((CalendarSlot.master_id == master_id) | (CalendarSlot.master_id.is_(None)))
    busy = await session.scalar(query.limit(1))
    return busy is not None


async def list_free_slots(session: AsyncSession, master_id: int | None = None, limit: int = 6) -> list[tuple[datetime, datetime]]:
    free: list[tuple[datetime, datetime]] = []
    for starts_at, ends_at in _business_candidates():
        if not await is_slot_busy(session, starts_at, ends_at, master_id):
            free.append((starts_at, ends_at))
            if len(free) >= limit:
                break
    return free


async def reserve_slot(
    session: AsyncSession,
    ticket_id: int,
    starts_at: datetime,
    ends_at: datetime,
    master_id: int | None = None,
    replace_existing: bool = True,
) -> CalendarSlot:
    if await is_slot_busy(session, starts_at, ends_at, master_id):
        raise RuntimeError("Calendar slot is busy")

    if replace_existing:
        existing = (await session.scalars(select(CalendarSlot).where(CalendarSlot.ticket_id == ticket_id))).all()
        for slot in existing:
            if slot.status in {CalendarSlotStatus.RESERVED, CalendarSlotStatus.BUSY}:
                slot.status = CalendarSlotStatus.CANCELLED

    slot = CalendarSlot(
        ticket_id=ticket_id,
        master_id=master_id,
        starts_at=starts_at,
        ends_at=ends_at,
        status=CalendarSlotStatus.RESERVED,
    )
    session.add(slot)
    await session.flush()
    return slot


async def reserve_next_slot(session: AsyncSession, ticket_id: int, master_id: int | None = None) -> CalendarSlot:
    free = await list_free_slots(session, master_id=master_id, limit=1)
    if not free:
        raise RuntimeError(f"No free calendar slots for next {settings.slot_search_days} days")
    starts_at, ends_at = free[0]
    return await reserve_slot(session, ticket_id, starts_at, ends_at, master_id)
