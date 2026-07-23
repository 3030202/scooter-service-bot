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


async def get_master_daily_workload(session: AsyncSession, master_id: int | None, target_date: datetime.date | None = None) -> dict:
    if target_date is None:
        target_date = datetime.now(service_tz()).date()

    tz = service_tz()
    start_dt = to_utc_naive(datetime.combine(target_date, time(0, 0), tz))
    end_dt = to_utc_naive(datetime.combine(target_date, time(23, 59, 59), tz))

    query = select(CalendarSlot).where(
        CalendarSlot.starts_at >= start_dt,
        CalendarSlot.ends_at <= end_dt,
        CalendarSlot.status.in_([CalendarSlotStatus.RESERVED, CalendarSlotStatus.BUSY, CalendarSlotStatus.DONE]),
    )
    if master_id is not None:
        query = query.where(CalendarSlot.master_id == master_id)

    slots = (await session.scalars(query)).all()
    total_minutes = sum((slot.ends_at - slot.starts_at).total_seconds() / 60.0 for slot in slots)
    workday_hours = (settings.workday_end_hour - settings.workday_start_hour)
    workday_minutes = max(workday_hours * 60.0, 1.0)
    percent = min(100, int((total_minutes / workday_minutes) * 100))

    return {
        "master_id": master_id,
        "date": target_date,
        "total_hours": round(total_minutes / 60.0, 1),
        "capacity_percent": percent,
        "slots_count": len(slots),
        "slots": slots,
    }


async def recommend_smart_slot(session: AsyncSession, duration_minutes: int = 120) -> tuple[int | None, datetime, datetime]:
    free_candidates = await list_free_slots(session, limit=5)
    if not free_candidates:
        raise RuntimeError("No free slots available")

    starts_at, ends_at = free_candidates[0]
    return None, starts_at, ends_at


async def block_master_slot(
    session: AsyncSession,
    master_id: int,
    starts_at: datetime,
    ends_at: datetime,
    reason: str = "Административный перерыв",
) -> CalendarSlot:
    if await is_slot_busy(session, starts_at, ends_at, master_id):
        raise RuntimeError("Slot is already busy")

    slot = CalendarSlot(
        ticket_id=None,
        master_id=master_id,
        starts_at=starts_at,
        ends_at=ends_at,
        status=CalendarSlotStatus.BUSY,
        note=reason,
    )
    session.add(slot)
    await session.flush()
    return slot


def render_master_workload_card(masters_workload: list[dict]) -> str:
    lines = ["📅 ЗАГРУЗКА МАСТЕРСКОЙ", ""]
    for wl in masters_workload:
        master_name = wl.get("master_name", f"Мастер #{wl.get('master_id')}")
        percent = wl.get("capacity_percent", 0)
        hours = wl.get("total_hours", 0.0)

        filled = int(percent / 10)
        empty = 10 - filled
        bar = "🟩" * filled + "⬜" * empty

        lines.append(f"👤 {master_name}:")
        lines.append(f"  {bar} {percent}% ({hours} ч / {wl.get('slots_count', 0)} слотов)")
        lines.append("")

    return "\n".join(lines)
