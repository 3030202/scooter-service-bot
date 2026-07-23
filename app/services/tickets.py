from decimal import Decimal
from typing import Any

from app.db.models import Ticket, TicketStatus, User

STATUS_LABELS = {
    TicketStatus.DRAFT: "черновик",
    TicketStatus.WAITING_PHOTOS: "ждем фото",
    TicketStatus.AI_ANALYSIS: "AI-диагностика",
    TicketStatus.DIAGNOSED: "диагностика готова",
    TicketStatus.NEW: "новая",
    TicketStatus.ACCEPTED: "принята",
    TicketStatus.ASSIGNED: "мастер назначен",
    TicketStatus.WAITING_APPROVAL: "ожидает подтверждения",
    TicketStatus.PRICE_OFFERED: "цена предложена",
    TicketStatus.CLIENT_APPROVED: "клиент подтвердил",
    TicketStatus.IN_PROGRESS: "в работе",
    TicketStatus.DONE: "готово",
    TicketStatus.CANCELLED: "отменена",
}


def format_price(value: Any) -> str:
    if value is None:
        return "по диагностике"
    try:
        amount = Decimal(str(value))
        if amount == amount.to_integral_value():
            return str(int(amount))
        return f"{amount:.2f}"
    except Exception:
        return str(value)


def status_label(status: TicketStatus) -> str:
    return STATUS_LABELS.get(status, status.value)


def final_price_text(ticket: Ticket) -> str:
    price = format_price(ticket.final_price)
    eta = ticket.final_eta or "после диагностики"
    return f"{price} RUB / {eta}"


def ai_price_text(ticket: Ticket) -> str:
    return f"{format_price(ticket.ai_price_min)}–{format_price(ticket.ai_price_max)} RUB / {ticket.ai_eta or 'после диагностики'}"


def build_client_preview(ticket: Ticket, slot_text: str) -> str:
    return (
        f"🧾 Предварительная заявка #{ticket.id}\n\n"
        f"Вероятная неисправность: {ticket.ai_fault or 'требуется диагностика'}\n"
        f"AI-оценка: {ai_price_text(ticket)}\n"
        f"Слот: {slot_text}\n\n"
        "Подтвердите заявку, чтобы отправить ее мастерам."
    )


def build_final_offer(ticket: Ticket) -> str:
    return (
        f"💰 Финальное предложение по заявке #{ticket.id}\n\n"
        f"Стоимость и срок: {final_price_text(ticket)}\n\n"
        "Подтвердите, если условия подходят. После подтверждения мастер сможет начать работу."
    )


def build_ticket_card(ticket: Ticket, client: User | None = None, slot_text: str | None = None) -> str:
    lines = [
        f"🧾 Заявка #{ticket.id}",
        f"Статус: {status_label(ticket.status)}",
    ]
    if client:
        username = f"@{client.username}" if client.username else "без username"
        lines.extend([
            f"Клиент: {client.full_name or 'без имени'} / {username}",
            f"Телефон: {client.phone or 'не указан'}",
        ])
    if ticket.description:
        lines.extend(["", f"Описание: {ticket.description}"])
    lines.extend([
        "",
        f"AI: {ticket.ai_fault or 'нет данных'}",
        f"AI-оценка: {ai_price_text(ticket)}",
        f"Финально: {final_price_text(ticket) if ticket.final_price or ticket.final_eta else 'еще не выставлено'}",
    ])
    if slot_text:
        lines.append(f"Слот: {slot_text}")
    return "\n".join(lines)


def parse_price_eta(text: str) -> tuple[Decimal, str]:
    raw = text.strip().replace(",", ".")
    if not raw:
        raise ValueError("empty")
    if ";" in raw:
        price_raw, eta = raw.split(";", 1)
    elif "\n" in raw:
        price_raw, eta = raw.split("\n", 1)
    else:
        parts = raw.split(maxsplit=1)
        price_raw = parts[0]
        eta = parts[1] if len(parts) > 1 else "после диагностики"
    price = Decimal(price_raw.strip())
    if price <= 0:
        raise ValueError("price")
    return price, eta.strip() or "после диагностики"
