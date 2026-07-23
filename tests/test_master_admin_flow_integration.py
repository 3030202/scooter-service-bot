from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import ServiceCatalogItem, Ticket, TicketServiceItem, TicketStatus, UserRole
from app.services.catalog import attach_catalog_item, list_catalog, recompute_ticket_price


@pytest.mark.asyncio
async def test_catalog_line_items_attachment(db_session, client_user):
    ticket = Ticket(
        client_id=client_user.id,
        status=TicketStatus.ASSIGNED,
        description="Ремонт тормозной системы",
    )
    db_session.add(ticket)
    await db_session.commit()

    catalog_items = await list_catalog(db_session, limit=10)
    assert len(catalog_items) > 0

    item1 = catalog_items[0]
    item2 = catalog_items[1] if len(catalog_items) > 1 else catalog_items[0]

    line1 = await attach_catalog_item(db_session, ticket, item1, source="catalog")
    line2 = await attach_catalog_item(db_session, ticket, item2, source="catalog")
    await db_session.commit()

    service_items = (await db_session.scalars(
        select(TicketServiceItem).where(TicketServiceItem.ticket_id == ticket.id)
    )).all()
    assert len(service_items) >= 1

    computed_price = await recompute_ticket_price(db_session, ticket)
    assert computed_price > 0
    assert ticket.final_price == computed_price


@pytest.mark.asyncio
async def test_admin_queue_filtering(db_session, client_user, master_user):
    t1 = Ticket(client_id=client_user.id, status=TicketStatus.NEW, description="Новая 1")
    t2 = Ticket(client_id=client_user.id, master_id=master_user.id, status=TicketStatus.IN_PROGRESS, description="В работе 1")
    t3 = Ticket(client_id=client_user.id, status=TicketStatus.DONE, description="Готовая 1")
    db_session.add_all([t1, t2, t3])
    await db_session.commit()

    new_tickets = (await db_session.scalars(
        select(Ticket).where(Ticket.status == TicketStatus.NEW)
    )).all()
    assert any(t.id == t1.id for t in new_tickets)

    progress_tickets = (await db_session.scalars(
        select(Ticket).where(Ticket.status == TicketStatus.IN_PROGRESS)
    )).all()
    assert any(t.id == t2.id for t in progress_tickets)
