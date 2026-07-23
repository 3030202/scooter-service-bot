import pytest

from app.db.models import Ticket, TicketStatus
from app.services.crm import client_summary, get_or_create_profile, update_profile_after_ticket_done


@pytest.mark.asyncio
async def test_client_summary_and_profile(db_session, client_user):
    profile = await get_or_create_profile(db_session, client_user)
    assert profile is not None
    assert profile.user_id == client_user.id
    assert profile.loyalty_tag == "new"

    ticket = Ticket(
        client_id=client_user.id,
        status=TicketStatus.DONE,
        final_price=6000.0,
        description="Капитальный ремонт АКБ",
        ai_fault="Сгорели элементы 18650",
    )
    db_session.add(ticket)
    await db_session.commit()

    updated_profile = await update_profile_after_ticket_done(db_session, ticket)
    await db_session.commit()

    assert updated_profile.loyalty_tag == "high_value"
    assert updated_profile.repairs_count == 1

    summary_text = await client_summary(db_session, client_user)
    assert "Клиент: Иван Клиент" in summary_text
    assert "6000" in summary_text
    assert "high_value" in summary_text


@pytest.mark.asyncio
async def test_client_repeat_ticket_draft(db_session, client_user):
    original_ticket = Ticket(
        client_id=client_user.id,
        status=TicketStatus.DONE,
        description="Замена камеры переднего колеса",
    )
    db_session.add(original_ticket)
    await db_session.commit()

    repeat_ticket = Ticket(
        client_id=client_user.id,
        status=TicketStatus.DRAFT,
        description=f"Повторная заявка на основе #{original_ticket.id}: {original_ticket.description}",
    )
    db_session.add(repeat_ticket)
    await db_session.commit()

    assert repeat_ticket.id is not None
    assert repeat_ticket.status == TicketStatus.DRAFT
    assert f"#{original_ticket.id}" in repeat_ticket.description
