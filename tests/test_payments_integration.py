from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import PaymentStatus, PaymentTransaction, Ticket, TicketStatus, TicketServiceItem
from app.services.payments import build_invoice_payload, record_successful_payment


@pytest.mark.asyncio
async def test_build_invoice_payload(db_session, client_user):
    ticket = Ticket(
        client_id=client_user.id,
        status=TicketStatus.PRICE_OFFERED,
        final_price=Decimal("4500.00"),
        description="Замена контроллера 36V",
    )
    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    item1 = TicketServiceItem(
        ticket_id=ticket.id,
        title="Контроллер 36V",
        price=Decimal("3000.00"),
        qty=1,
    )
    item2 = TicketServiceItem(
        ticket_id=ticket.id,
        title="Работа по замене",
        price=Decimal("1500.00"),
        qty=1,
    )
    db_session.add_all([item1, item2])
    await db_session.commit()

    params = build_invoice_payload(ticket, [item1, item2])
    assert params["title"] == f"Оплата ремонта #{ticket.id}"
    assert params["payload"] == f"ticket_payment_{ticket.id}"
    assert params["currency"] == "RUB"
    assert len(params["prices"]) == 2
    assert params["prices"][0].amount == 300000
    assert params["prices"][1].amount == 150000


@pytest.mark.asyncio
async def test_record_successful_payment(db_session, client_user):
    ticket = Ticket(
        client_id=client_user.id,
        status=TicketStatus.PRICE_OFFERED,
        final_price=Decimal("5000.00"),
        description="Замена мотор-колеса",
    )
    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    txn = await record_successful_payment(
        session=db_session,
        ticket_id=ticket.id,
        telegram_charge_id="tg_charge_abc999",
        provider_charge_id="prov_charge_xyz888",
        amount=5000.0,
        currency="RUB",
    )
    await db_session.commit()

    assert txn.id is not None
    assert txn.ticket_id == ticket.id
    assert txn.amount == 5000.0
    assert txn.telegram_payment_charge_id == "tg_charge_abc999"

    ticket_db = await db_session.get(Ticket, ticket.id)
    assert ticket_db.payment_status == PaymentStatus.PAID
    assert ticket_db.payment_id == "tg_charge_abc999"
    assert ticket_db.status == TicketStatus.CLIENT_APPROVED
