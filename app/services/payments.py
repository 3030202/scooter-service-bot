from decimal import Decimal

from aiogram.types import LabeledPrice
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import PaymentStatus, PaymentTransaction, Ticket, TicketStatus, TicketServiceItem


def build_invoice_payload(ticket: Ticket, items: list[TicketServiceItem] | None = None) -> dict:
    title = f"Оплата ремонта #{ticket.id}"
    description = (ticket.description or "Сервисное обслуживание самоката")[:255]
    payload = f"ticket_payment_{ticket.id}"
    provider_token = settings.payment_provider_token

    prices: list[LabeledPrice] = []
    if items:
        for item in items:
            amount_cents = int(round(float(item.price) * item.qty * 100))
            prices.append(LabeledPrice(label=f"{item.title} (x{item.qty})"[:32], amount=max(amount_cents, 100)))
    else:
        price_val = float(ticket.final_price) if ticket.final_price else 100.0
        amount_cents = int(round(price_val * 100))
        prices.append(LabeledPrice(label=f"Ремонт #{ticket.id}", amount=max(amount_cents, 100)))

    return {
        "title": title,
        "description": description,
        "payload": payload,
        "provider_token": provider_token,
        "currency": "RUB",
        "prices": prices,
        "start_parameter": f"pay-ticket-{ticket.id}",
    }


async def record_successful_payment(
    session: AsyncSession,
    ticket_id: int,
    telegram_charge_id: str,
    provider_charge_id: str | None,
    amount: float,
    currency: str = "RUB",
) -> PaymentTransaction:
    ticket = await session.get(Ticket, ticket_id)
    if not ticket:
        raise ValueError(f"Ticket #{ticket_id} not found")

    ticket.payment_status = PaymentStatus.PAID
    ticket.payment_id = telegram_charge_id
    ticket.status = TicketStatus.CLIENT_APPROVED

    txn = PaymentTransaction(
        ticket_id=ticket.id,
        amount=amount,
        currency=currency,
        telegram_payment_charge_id=telegram_charge_id,
        provider_payment_charge_id=provider_charge_id,
    )
    session.add(txn)
    await session.flush()
    return txn
