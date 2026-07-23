from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import ClientProfile, Media, MediaType, RetentionReminder, Ticket, TicketStatus, User
from app.services.crm import create_retention_after_done, update_profile_after_ticket_done


@pytest.mark.asyncio
async def test_full_ticket_lifecycle_draft_to_done(db_session, client_user, master_user):
    # 1. Draft creation
    ticket = Ticket(
        client_id=client_user.id,
        status=TicketStatus.DRAFT,
        description="Не включается самокат Xiaomi 1S, дисплей мигает",
    )
    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)
    assert ticket.id is not None
    assert ticket.status == TicketStatus.DRAFT

    # 2. Attach Media
    media = Media(
        ticket_id=ticket.id,
        type=MediaType.PHOTO,
        telegram_file_id="file_abc123",
        telegram_file_unique_id="unique_abc123",
        local_path="photos/1/unique_abc123.jpg",
    )
    db_session.add(media)
    ticket.status = TicketStatus.WAITING_PHOTOS
    await db_session.commit()

    media_items = (await db_session.scalars(select(Media).where(Media.ticket_id == ticket.id))).all()
    assert len(media_items) == 1

    # 3. AI Diagnostics & Confirmation
    ticket.status = TicketStatus.AI_ANALYSIS
    ticket.ai_fault = "Поломка контроллера или BMS платы"
    ticket.ai_price_min = Decimal("2500")
    ticket.ai_price_max = Decimal("5000")
    ticket.ai_eta = "1-2 дня"
    ticket.status = TicketStatus.DIAGNOSED
    await db_session.commit()

    # 4. Client confirms -> status NEW
    ticket.status = TicketStatus.NEW
    await db_session.commit()
    assert ticket.status == TicketStatus.NEW

    # 5. Master assigns ticket -> status ASSIGNED
    ticket.master_id = master_user.id
    ticket.status = TicketStatus.ASSIGNED
    await db_session.commit()
    assert ticket.master_id == master_user.id

    # 6. Master offers price & ETA -> status PRICE_OFFERED
    ticket.final_price = Decimal("3500.00")
    ticket.final_eta = "1 день"
    ticket.status = TicketStatus.PRICE_OFFERED
    await db_session.commit()
    assert ticket.status == TicketStatus.PRICE_OFFERED

    # 7. Client approves final price -> status CLIENT_APPROVED
    ticket.status = TicketStatus.CLIENT_APPROVED
    await db_session.commit()
    assert ticket.status == TicketStatus.CLIENT_APPROVED

    # 8. Master starts work -> IN_PROGRESS
    ticket.status = TicketStatus.IN_PROGRESS
    await db_session.commit()
    assert ticket.status == TicketStatus.IN_PROGRESS

    # 9. Master completes work -> DONE
    ticket.status = TicketStatus.DONE
    profile = await update_profile_after_ticket_done(db_session, ticket)
    retention = await create_retention_after_done(db_session, ticket)
    await db_session.commit()

    # Verify CRM & Retention side effects
    assert profile is not None
    assert profile.repairs_count == 1
    assert Decimal(str(profile.total_spent)) == Decimal("3500.00")
    assert profile.last_issue_summary == "Поломка контроллера или BMS платы"

    retention_db = await db_session.scalar(select(RetentionReminder).where(RetentionReminder.ticket_id == ticket.id))
    assert retention_db is not None
    assert retention_db.is_sent is False
    assert retention_db.client_id == client_user.id


@pytest.mark.asyncio
async def test_ticket_cancellation_flow(db_session, client_user):
    ticket = Ticket(
        client_id=client_user.id,
        status=TicketStatus.NEW,
        description="Заявка для отмены",
    )
    db_session.add(ticket)
    await db_session.commit()

    ticket.status = TicketStatus.CANCELLED
    await db_session.commit()

    ticket_db = await db_session.get(Ticket, ticket.id)
    assert ticket_db.status == TicketStatus.CANCELLED
