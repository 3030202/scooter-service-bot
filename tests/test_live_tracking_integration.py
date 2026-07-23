import pytest
from sqlalchemy import select

from app.db.models import RepairJournalEntry, RepairStage, Ticket, TicketStatus
from app.services.tickets import build_live_ticket_card, render_live_progress_bar


@pytest.mark.asyncio
async def test_render_live_progress_bar():
    bar_received = render_live_progress_bar(RepairStage.RECEIVED)
    assert "🟨 Приемка" in bar_received
    assert "⬜ Диагностика" in bar_received

    bar_assembly = render_live_progress_bar(RepairStage.ASSEMBLY)
    assert "🟩 Приемка" in bar_assembly
    assert "🟩 Диагностика" in bar_assembly
    assert "🟨 Сборка" in bar_assembly
    assert "⬜ Тесты" in bar_assembly

    bar_ready = render_live_progress_bar(RepairStage.READY)
    assert "🟩 Приемка" in bar_ready
    assert "🟩 Диагностика" in bar_ready
    assert "🟩 Запчасти" in bar_ready
    assert "🟩 Сборка" in bar_ready
    assert "🟩 Тесты" in bar_ready
    assert "🟨 Выдача" in bar_ready


@pytest.mark.asyncio
async def test_stage_transitions_and_journal_entries(db_session, client_user):
    ticket = Ticket(
        client_id=client_user.id,
        status=TicketStatus.IN_PROGRESS,
        repair_stage=RepairStage.RECEIVED,
        description="Замена BMS платы",
    )
    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    # 1. Advance stage to ASSEMBLY
    ticket.repair_stage = RepairStage.ASSEMBLY
    entry1 = RepairJournalEntry(
        ticket_id=ticket.id,
        stage=RepairStage.ASSEMBLY,
        comment="Старый контроллер снят, установлена новая плата BMS",
        photo_file_id="photo_file_bms_123",
    )
    db_session.add(entry1)
    await db_session.commit()

    # 2. Query entries
    entries = (await db_session.scalars(
        select(RepairJournalEntry).where(RepairJournalEntry.ticket_id == ticket.id)
    )).all()
    assert len(entries) == 1
    assert entries[0].comment == "Старый контроллер снят, установлена новая плата BMS"
    assert entries[0].photo_file_id == "photo_file_bms_123"

    # 3. Build card
    card_text = build_live_ticket_card(ticket, entries)
    assert "LIVE-ТРЕКИНГ" in card_text
    assert "🟨 Сборка" in card_text
    assert "Старый контроллер снят" in card_text


@pytest.mark.asyncio
async def test_client_pickup_method_selection(db_session, client_user):
    ticket = Ticket(
        client_id=client_user.id,
        status=TicketStatus.CLIENT_APPROVED,
        pickup_method="self_pickup",
    )
    db_session.add(ticket)
    await db_session.commit()

    ticket.pickup_method = "courier"
    await db_session.commit()

    ticket_db = await db_session.get(Ticket, ticket.id)
    assert ticket_db.pickup_method == "courier"
