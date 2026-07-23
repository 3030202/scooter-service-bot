from decimal import Decimal
from typing import Any

from app.db.models import RepairJournalEntry, RepairStage, Ticket, TicketStatus, User

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

STAGE_LABELS = {
    RepairStage.RECEIVED: "Принят в сервис",
    RepairStage.DIAGNOSTICS: "Диагностика",
    RepairStage.PARTS_ORDERING: "Заказ запчастей",
    RepairStage.ASSEMBLY: "Сборка / Пайка",
    RepairStage.TESTING: "Тестирование",
    RepairStage.READY: "Готов к выдаче",
}

STAGE_ORDER = [
    RepairStage.RECEIVED,
    RepairStage.DIAGNOSTICS,
    RepairStage.PARTS_ORDERING,
    RepairStage.ASSEMBLY,
    RepairStage.TESTING,
    RepairStage.READY,
]


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


def render_live_progress_bar(current_stage: RepairStage | str) -> str:
    current_val = current_stage.value if hasattr(current_stage, "value") else str(current_stage)

    stage_icons = {
        RepairStage.RECEIVED.value: "Приемка",
        RepairStage.DIAGNOSTICS.value: "Диагностика",
        RepairStage.PARTS_ORDERING.value: "Запчасти",
        RepairStage.ASSEMBLY.value: "Сборка",
        RepairStage.TESTING.value: "Тесты",
        RepairStage.READY.value: "Выдача",
    }

    try:
        current_idx = [s.value for s in STAGE_ORDER].index(current_val)
    except ValueError:
        current_idx = 0

    parts = []
    for idx, stage in enumerate(STAGE_ORDER):
        label = stage_icons.get(stage.value, stage.value)
        if idx < current_idx:
            parts.append(f"🟩 {label}")
        elif idx == current_idx:
            parts.append(f"🟨 {label}")
        else:
            parts.append(f"⬜ {label}")

    return " ➔ ".join(parts)


def build_live_ticket_card(ticket: Ticket, journal_entries: list[RepairJournalEntry] | None = None) -> str:
    stage = ticket.repair_stage or RepairStage.RECEIVED
    progress_bar = render_live_progress_bar(stage)
    pickup = "Самовывоз" if (ticket.pickup_method or "self_pickup") == "self_pickup" else "Доставка курьером"

    lines = [
        f"📍 LIVE-ТРЕКИНГ ЗАЯВКИ #{ticket.id}",
        f"Текущий этап: {STAGE_LABELS.get(stage, stage.value)}",
        "",
        progress_bar,
        "",
        f"Способ получения: {pickup}",
        f"Финальная цена: {final_price_text(ticket)}",
    ]

    if journal_entries:
        lines.extend(["", "📸 Дневник работ мастера:"])
        for entry in journal_entries:
            dt_str = entry.created_at.strftime("%d.%m %H:%M") if entry.created_at else ""
            comment_str = f" — {entry.comment}" if entry.comment else ""
            lines.append(f"• [{dt_str}] {STAGE_LABELS.get(entry.stage, entry.stage.value)}{comment_str}")

    return "\n".join(lines)
