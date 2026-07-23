from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import CalendarSlotStatus
from app.services.calendar import block_master_slot, get_master_daily_workload, is_slot_busy, render_master_workload_card, reserve_slot


@pytest.mark.asyncio
async def test_get_master_daily_workload_and_reservation(db_session, master_user, client_user):
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    start_dt = now_utc + timedelta(hours=1)
    end_dt = start_dt + timedelta(hours=2)

    # 1. Reserve slot
    slot = await reserve_slot(db_session, ticket_id=1, starts_at=start_dt, ends_at=end_dt, master_id=master_user.id)
    await db_session.commit()

    assert slot.id is not None
    assert slot.master_id == master_user.id

    # 2. Get workload
    wl = await get_master_daily_workload(db_session, master_id=master_user.id, target_date=now_utc.date())
    assert wl["slots_count"] >= 1
    assert wl["total_hours"] >= 2.0


@pytest.mark.asyncio
async def test_block_master_slot(db_session, master_user):
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    start_dt = now_utc + timedelta(hours=3)
    end_dt = start_dt + timedelta(hours=1)

    blocked_slot = await block_master_slot(
        db_session,
        master_id=master_user.id,
        starts_at=start_dt,
        ends_at=end_dt,
        reason="Обед / перерыв",
    )
    await db_session.commit()

    assert blocked_slot.status == CalendarSlotStatus.BUSY
    assert blocked_slot.note == "Обед / перерыв"

    busy = await is_slot_busy(db_session, start_dt, end_dt, master_id=master_user.id)
    assert busy is True


@pytest.mark.asyncio
async def test_render_master_workload_card():
    workloads = [
        {"master_name": "Пётр Мастер", "capacity_percent": 50, "total_hours": 4.5, "slots_count": 3},
        {"master_name": "Иван Техник", "capacity_percent": 20, "total_hours": 1.8, "slots_count": 1},
    ]
    card_text = render_master_workload_card(workloads)
    assert "ЗАГРУЗКА МАСТЕРСКОЙ" in card_text
    assert "Пётр Мастер:" in card_text
    assert "50%" in card_text
    assert "4.5 ч" in card_text
