from datetime import datetime, timedelta, timezone
from decimal import Decimal

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import desc, func, select

from app.config import settings
from app.db.models import CalendarSlot, CalendarSlotStatus, RepairJournalEntry, RepairStage, Ticket, TicketStatus, TicketServiceItem, User, UserRole
from app.db.session import AsyncSessionLocal
from app.keyboards.inline import (
    admin_assign_keyboard,
    admin_queue_keyboard,
    admin_slot_keyboard,
    back_to_menu_keyboard,
    client_final_offer_keyboard,
    client_done_keyboard,
    catalog_items_keyboard,
    admin_catalog_keyboard,
    retention_keyboard,
    master_ticket_keyboard,
    master_stage_keyboard,
    admin_schedule_keyboard,
    master_schedule_keyboard,
    admin_ai_providers_keyboard,
)
from app.db.models import AIModel, AIProvider, CalendarSlot, CalendarSlotStatus, RepairJournalEntry, RepairStage, Ticket, TicketStatus, TicketServiceItem, User, UserRole
from app.services.ai_provider_service import sync_provider_models
from app.services.calendar import format_slot, get_master_daily_workload, list_free_slots, render_master_workload_card, reserve_slot
from app.services.metrics import metrics
from app.services.catalog import attach_catalog_item, list_catalog, match_catalog, recompute_ticket_price, seed_catalog
from app.services.crm import client_summary, create_retention_after_done, due_retention_items, update_profile_after_ticket_done
from app.services.tickets import STAGE_LABELS, build_final_offer, build_ticket_card, parse_price_eta, render_live_progress_bar, status_label

router = Router()

ACTIVE_STATUSES = [
    TicketStatus.NEW,
    TicketStatus.ASSIGNED,
    TicketStatus.PRICE_OFFERED,
    TicketStatus.CLIENT_APPROVED,
    TicketStatus.IN_PROGRESS,
]
QUEUE_FILTERS = {
    "all": [TicketStatus.NEW, TicketStatus.ASSIGNED, TicketStatus.PRICE_OFFERED, TicketStatus.CLIENT_APPROVED, TicketStatus.IN_PROGRESS],
    "new": [TicketStatus.NEW, TicketStatus.ASSIGNED],
    "price": [TicketStatus.PRICE_OFFERED],
    "approved": [TicketStatus.CLIENT_APPROVED],
    "work": [TicketStatus.IN_PROGRESS],
}


class MasterFSM(StatesGroup):
    waiting_offer = State()


class MasterJournalFSM(StatesGroup):
    waiting_photo = State()


def is_authorized_master(telegram_id: int) -> bool:
    return telegram_id in settings.master_telegram_ids or telegram_id in settings.admin_telegram_ids


def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.admin_telegram_ids


async def get_or_create_staff_user(callback_or_message, session) -> User:
    from_user = callback_or_message.from_user
    role = UserRole.ADMIN if is_admin(from_user.id) else UserRole.MASTER
    user = await session.scalar(select(User).where(User.telegram_id == from_user.id))
    if user:
        user.username = from_user.username
        user.full_name = from_user.full_name
        if user.role != UserRole.ADMIN:
            user.role = role
        return user
    user = User(
        telegram_id=from_user.id,
        username=from_user.username,
        full_name=from_user.full_name,
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def get_or_create_master_by_telegram_id(session, telegram_id: int) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user:
        if user.role == UserRole.CLIENT:
            user.role = UserRole.MASTER
        return user
    user = User(telegram_id=telegram_id, username=None, full_name=f"Master {telegram_id}", role=UserRole.MASTER)
    session.add(user)
    await session.flush()
    return user


async def notify_client(bot: Bot, ticket: Ticket, session, text: str, with_offer_keyboard: bool = False) -> None:
    client = await session.get(User, ticket.client_id)
    if not client:
        return
    keyboard = client_final_offer_keyboard(ticket.id) if with_offer_keyboard else None
    await bot.send_message(client.telegram_id, text, reply_markup=keyboard)


@router.callback_query(F.data == "menu:my_jobs")
async def my_jobs(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_authorized_master(callback.from_user.id):
        await callback.answer("Доступ только для мастеров.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        master = await get_or_create_staff_user(callback, session)
        await session.commit()
        tickets = (await session.scalars(
            select(Ticket)
            .where(Ticket.master_id == master.id, Ticket.status.in_(ACTIVE_STATUSES))
            .order_by(desc(Ticket.updated_at))
            .limit(10)
        )).all()

    if not tickets:
        await callback.message.answer("Активных работ нет.", reply_markup=back_to_menu_keyboard())
        await callback.answer()
        return

    for ticket in tickets:
        await callback.message.answer(
            build_ticket_card(ticket),
            reply_markup=master_ticket_keyboard(ticket.id, assigned_to_me=True, is_admin=is_admin(callback.from_user.id)),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:queue"))
async def admin_queue(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return

    parts = callback.data.split(":")
    filter_name = parts[2] if len(parts) > 2 else "all"
    statuses = QUEUE_FILTERS.get(filter_name, QUEUE_FILTERS["all"])

    async with AsyncSessionLocal() as session:
        tickets = (await session.scalars(
            select(Ticket).where(Ticket.status.in_(statuses)).order_by(desc(Ticket.created_at)).limit(20)
        )).all()

    if not tickets:
        await callback.message.answer("Очередь пуста.", reply_markup=back_to_menu_keyboard())
        await callback.answer()
        return

    text = "🧭 Очередь сервиса:\n\n" + "\n".join(f"#{ticket.id} — {status_label(ticket.status)}" for ticket in tickets)
    await callback.message.answer(text, reply_markup=admin_queue_keyboard([ticket.id for ticket in tickets], filter_name))
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.stale_ticket_minutes)
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status))).all()
        stale_count = await session.scalar(
            select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.NEW, Ticket.created_at < cutoff)
        )
        free_slots = await list_free_slots(session, limit=5)

    lines = ["📊 Операционный статус", ""]
    for status, count in rows:
        lines.append(f"{status_label(status)}: {count}")
    lines.extend(["", f"Зависшие новые > {settings.stale_ticket_minutes} мин: {stale_count or 0}", "", "Ближайшие свободные слоты:"])
    lines.extend([f"• {format_slot(type('SlotPreview', (), {'starts_at': s, 'ends_at': e})())}" for s, e in free_slots] or ["• нет слотов"])
    await callback.message.answer("\n".join(lines), reply_markup=back_to_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:view:"))
async def admin_view_ticket(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return

    ticket_id = int(callback.data.rsplit(":", 1)[1])
    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        client = await session.get(User, ticket.client_id)
        slot = await session.scalar(select(CalendarSlot).where(CalendarSlot.ticket_id == ticket.id).order_by(desc(CalendarSlot.starts_at)).limit(1))
        text = build_ticket_card(ticket, client, format_slot(slot))

    await callback.message.answer(text, reply_markup=master_ticket_keyboard(ticket_id, is_admin=True))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:client:"))
async def admin_client_card(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return
    ticket_id = int(callback.data.rsplit(":", 1)[1])
    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        client = await session.get(User, ticket.client_id)
        if not client:
            await callback.answer("Клиент не найден", show_alert=True)
            return
        text = await client_summary(session, client)
        await session.commit()
    await callback.message.answer(text, reply_markup=back_to_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:assign_menu:"))
async def admin_assign_menu(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return
    ticket_id = int(callback.data.rsplit(":", 1)[1])
    if not settings.master_telegram_ids:
        await callback.answer("MASTER_TELEGRAM_IDS пустой", show_alert=True)
        return
    await callback.message.answer("Выберите мастера:", reply_markup=admin_assign_keyboard(ticket_id, settings.master_telegram_ids))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:assign:"))
async def admin_assign(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return
    _, _, ticket_raw, master_tg_raw = callback.data.split(":")
    ticket_id = int(ticket_raw)
    master_tg_id = int(master_tg_raw)
    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        master = await get_or_create_master_by_telegram_id(session, master_tg_id)
        ticket.master_id = master.id
        ticket.status = TicketStatus.ASSIGNED
        slots = (await session.scalars(select(CalendarSlot).where(CalendarSlot.ticket_id == ticket.id))).all()
        for slot in slots:
            if slot.status == CalendarSlotStatus.RESERVED:
                slot.master_id = master.id
        client = await session.get(User, ticket.client_id)
        await session.commit()
    metrics.inc("admin_assignments_total")
    if client:
        await bot.send_message(client.telegram_id, f"🔧 По заявке #{ticket_id} назначен мастер.")
    await callback.message.answer(f"Заявка #{ticket_id} назначена мастеру {master_tg_id}.", reply_markup=master_ticket_keyboard(ticket_id, is_admin=True))
    await callback.answer("Назначено")


@router.callback_query(F.data.startswith("admin:slot_menu:"))
async def admin_slot_menu(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return
    ticket_id = int(callback.data.rsplit(":", 1)[1])
    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        slots = await list_free_slots(session, master_id=ticket.master_id, limit=8)
    if not slots:
        await callback.answer("Нет свободных слотов", show_alert=True)
        return
    await callback.message.answer("Выберите новый слот:", reply_markup=admin_slot_keyboard(ticket_id, slots))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:slot:"))
async def admin_set_slot(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return
    _, _, ticket_raw, ts_raw = callback.data.split(":")
    ticket_id = int(ticket_raw)
    starts_at = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
    ends_at = starts_at + timedelta(minutes=settings.slot_duration_minutes)
    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        slot = await reserve_slot(session, ticket.id, starts_at, ends_at, ticket.master_id)
        client = await session.get(User, ticket.client_id)
        await session.commit()
        await session.refresh(slot)
    if client:
        await bot.send_message(client.telegram_id, f"🕒 По заявке #{ticket_id} обновлен слот: {format_slot(slot)}")
    await callback.message.answer(f"Слот обновлен: {format_slot(slot)}", reply_markup=master_ticket_keyboard(ticket_id, is_admin=True))
    await callback.answer("Слот обновлен")


@router.callback_query(F.data.startswith("admin:cancel:"))
async def admin_cancel_ticket(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return
    ticket_id = int(callback.data.rsplit(":", 1)[1])
    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        ticket.status = TicketStatus.CANCELLED
        slots = (await session.scalars(select(CalendarSlot).where(CalendarSlot.ticket_id == ticket.id))).all()
        for slot in slots:
            if slot.status in {CalendarSlotStatus.RESERVED, CalendarSlotStatus.BUSY}:
                slot.status = CalendarSlotStatus.CANCELLED
        client = await session.get(User, ticket.client_id)
        await session.commit()
    metrics.inc("admin_cancelled_total")
    if client:
        await bot.send_message(client.telegram_id, f"🛑 Заявка #{ticket_id} отменена администратором.")
    await callback.message.answer(f"Заявка #{ticket_id} отменена.", reply_markup=back_to_menu_keyboard())
    await callback.answer("Отменена")


@router.callback_query(F.data == "admin:catalog")
async def admin_catalog(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return
    async with AsyncSessionLocal() as session:
        await seed_catalog(session)
        items = await list_catalog(session, limit=20)
        await session.commit()
    text = "📚 Каталог типовых работ:\n\n" + "\n".join(
        f"• {item.title}: {item.min_price or item.base_price}–{item.max_price or item.base_price} / {item.default_eta or 'срок уточняется'}"
        for item in items
    )
    await callback.message.answer(text, reply_markup=admin_catalog_keyboard(items))
    await callback.answer()


@router.callback_query(F.data.startswith("catalog:view:"))
async def admin_catalog_view(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return
    item_id = int(callback.data.rsplit(":", 1)[1])
    async with AsyncSessionLocal() as session:
        item = await session.get(__import__('app.db.models', fromlist=['ServiceCatalogItem']).ServiceCatalogItem, item_id)
        if not item:
            await callback.answer("Позиция не найдена", show_alert=True)
            return
    text = (
        f"📚 {item.title}\n\n"
        f"Категория: {item.category}\n"
        f"База: {item.base_price}\n"
        f"Диапазон: {item.min_price or item.base_price}–{item.max_price or item.base_price}\n"
        f"Срок: {item.default_eta or 'уточняется'}\n\n"
        f"Чек-лист мастера:\n{item.checklist or 'не задан'}"
    )
    await callback.message.answer(text, reply_markup=back_to_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:retention")
async def admin_retention(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return
    async with AsyncSessionLocal() as session:
        items = await due_retention_items(session, limit=10)
    if not items:
        await callback.message.answer("🔁 Сейчас нет due retention-напоминаний.", reply_markup=back_to_menu_keyboard())
        await callback.answer()
        return
    text = "🔁 Retention-очередь:\n\n" + "\n".join(f"#{r.id} — клиент {r.client_id}: {r.message}" for r in items)
    await callback.message.answer(text, reply_markup=retention_keyboard([r.id for r in items]))
    await callback.answer()


@router.callback_query(F.data.startswith("retention:send:"))
async def send_retention(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ только для админа.", show_alert=True)
        return
    reminder_id = int(callback.data.rsplit(":", 1)[1])
    async with AsyncSessionLocal() as session:
        reminder = await session.get(__import__('app.db.models', fromlist=['RetentionReminder']).RetentionReminder, reminder_id)
        if not reminder or reminder.is_sent:
            await callback.answer("Напоминание не найдено или уже отправлено", show_alert=True)
            return
        client = await session.get(User, reminder.client_id)
        if not client:
            await callback.answer("Клиент не найден", show_alert=True)
            return
        reminder.is_sent = True
        await session.commit()
    await bot.send_message(client.telegram_id, "🔧 Напоминание от сервиса: можно сделать быструю проверку после ремонта или сезонное ТО. Хотите создать заявку?")
    metrics.inc("retention_sent_total")
    await callback.message.answer(f"Retention-напоминание #{reminder_id} отправлено.", reply_markup=back_to_menu_keyboard())
    await callback.answer("Отправлено")


@router.callback_query(F.data.startswith("ticket:add_service:"))
async def add_catalog_service(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_authorized_master(callback.from_user.id):
        await callback.answer("Доступ только для мастеров.", show_alert=True)
        return
    _, _, ticket_raw, item_raw = callback.data.split(":")
    ticket_id = int(ticket_raw)
    item_id = int(item_raw)
    from app.db.models import ServiceCatalogItem
    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        item = await session.get(ServiceCatalogItem, item_id)
        if not ticket or not item:
            await callback.answer("Заявка или позиция не найдена", show_alert=True)
            return
        await attach_catalog_item(session, ticket, item, source="button")
        total = await recompute_ticket_price(session, ticket)
        await session.commit()
    metrics.inc("catalog_items_added_total")
    await callback.message.answer(f"➕ Добавлено: {item.title}. Текущая сумма: {total}.", reply_markup=master_ticket_keyboard(ticket_id, True, is_admin(callback.from_user.id)))
    await callback.answer("Добавлено")


@router.callback_query(F.data.startswith("ticket:"))
async def master_actions(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    if not callback.from_user or not is_authorized_master(callback.from_user.id):
        await callback.answer("Доступ только для авторизованных мастеров.", show_alert=True)
        return

    try:
        _, action, ticket_id_raw = callback.data.split(":")
        ticket_id = int(ticket_id_raw)
    except (ValueError, AttributeError):
        await callback.answer("Некорректная команда", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            await callback.answer("Заявка не найдена", show_alert=True)
            return

        master = await get_or_create_staff_user(callback, session)
        client = await session.get(User, ticket.client_id)

        if action == "assign":
            ticket.status = TicketStatus.ASSIGNED
            ticket.master_id = master.id
            slots = (await session.scalars(select(CalendarSlot).where(CalendarSlot.ticket_id == ticket.id))).all()
            for slot in slots:
                if slot.status == CalendarSlotStatus.RESERVED:
                    slot.master_id = master.id
            await session.commit()
            metrics.inc("master_assignments_total")
            if client:
                await bot.send_message(client.telegram_id, f"🔧 По заявке #{ticket.id} назначен мастер. Скоро пришлем финальную цену и срок.")
            await callback.message.answer(f"Заявка #{ticket.id} назначена на вас.", reply_markup=master_ticket_keyboard(ticket.id, True, is_admin(callback.from_user.id)))
            await callback.answer("Назначено")
            return

        if action == "offer_ai":
            ticket.master_id = ticket.master_id or master.id
            ticket.final_price = ticket.ai_price_max or ticket.ai_price_min
            ticket.final_eta = ticket.ai_eta or "после диагностики"
            ticket.status = TicketStatus.PRICE_OFFERED
            await session.commit()
            await session.refresh(ticket)
            metrics.inc("offers_sent_total")
            if client:
                await bot.send_message(client.telegram_id, build_final_offer(ticket), reply_markup=client_final_offer_keyboard(ticket.id))
            await callback.message.answer(f"AI-цена отправлена клиенту по заявке #{ticket.id}.", reply_markup=master_ticket_keyboard(ticket.id, True, is_admin(callback.from_user.id)))
            await callback.answer("Отправлено")
            return

        if action == "edit_offer":
            ticket.master_id = ticket.master_id or master.id
            await session.commit()
            await state.update_data(ticket_id=ticket.id)
            await state.set_state(MasterFSM.waiting_offer)
            await callback.message.answer(
                "Введите финальную цену и срок одним сообщением. Формат: `1500; 1 день`",
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard(),
            )
            await callback.answer()
            return

        if action == "catalog":
            await seed_catalog(session)
            text_for_match = " ".join([ticket.description or "", ticket.ai_fault or ""])
            matched = await match_catalog(session, text_for_match, limit=5)
            items = [m.item for m in matched] or await list_catalog(session, limit=10)
            await session.commit()
            text = "🧾 Выберите работу из каталога. Совпадения подобраны по описанию/AI-диагнозу."
            await callback.message.answer(text, reply_markup=catalog_items_keyboard(ticket.id, items))
            await callback.answer()
            return

        if action == "add_service":
            await callback.answer("Используйте кнопку позиции из каталога.", show_alert=True)
            return

        if action == "offer_catalog":
            total = await recompute_ticket_price(session, ticket)
            if total is None:
                await callback.answer("Сначала добавьте хотя бы одну работу из каталога.", show_alert=True)
                return
            ticket.master_id = ticket.master_id or master.id
            ticket.status = TicketStatus.PRICE_OFFERED
            await session.commit()
            await session.refresh(ticket)
            metrics.inc("catalog_offers_sent_total")
            if client:
                await bot.send_message(client.telegram_id, build_final_offer(ticket), reply_markup=client_final_offer_keyboard(ticket.id))
            await callback.message.answer(f"Каталожная цена {ticket.final_price} отправлена клиенту по заявке #{ticket.id}.", reply_markup=master_ticket_keyboard(ticket.id, True, is_admin(callback.from_user.id)))
            await callback.answer("Отправлено")
            return

        if action == "start_work":
            if ticket.status not in {TicketStatus.CLIENT_APPROVED, TicketStatus.IN_PROGRESS}:
                await callback.answer("Сначала клиент должен подтвердить финальную цену.", show_alert=True)
                return
            ticket.master_id = ticket.master_id or master.id
            ticket.status = TicketStatus.IN_PROGRESS
            active_slot = await session.scalar(
                select(CalendarSlot).where(CalendarSlot.ticket_id == ticket.id, CalendarSlot.status == CalendarSlotStatus.RESERVED).limit(1)
            )
            if active_slot:
                active_slot.status = CalendarSlotStatus.BUSY
            await session.commit()
            metrics.inc("work_started_total")
            if client:
                await bot.send_message(client.telegram_id, f"▶️ Работа по заявке #{ticket.id} началась.")
            await callback.message.answer(f"Заявка #{ticket.id} переведена в работу.", reply_markup=master_ticket_keyboard(ticket.id, True, is_admin(callback.from_user.id)))
            await callback.answer("В работе")
            return

        if action == "done":
            ticket.master_id = ticket.master_id or master.id
            ticket.status = TicketStatus.DONE
            slots = (await session.scalars(select(CalendarSlot).where(CalendarSlot.ticket_id == ticket.id))).all()
            for slot in slots:
                if slot.status in {CalendarSlotStatus.RESERVED, CalendarSlotStatus.BUSY}:
                    slot.status = CalendarSlotStatus.DONE
            await update_profile_after_ticket_done(session, ticket)
            await create_retention_after_done(session, ticket)
            await session.commit()
            metrics.inc("tickets_done_total")
            metrics.inc("retention_created_total")
            if client:
                await bot.send_message(client.telegram_id, f"🏁 Заявка #{ticket.id} завершена. Спасибо за обращение.", reply_markup=client_done_keyboard(ticket.id))
            await callback.message.answer(f"Заявка #{ticket.id} закрыта как готовая. CRM и retention обновлены.")
            await callback.answer("Готово")
            return

    await callback.answer("Неизвестное действие", show_alert=True)


@router.message(MasterFSM.waiting_offer, F.text)
async def receive_manual_offer(message: Message, bot: Bot, state: FSMContext) -> None:
    if not message.from_user or not is_authorized_master(message.from_user.id):
        await message.answer("Доступ только для мастеров.")
        return

    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not ticket_id:
        await state.clear()
        await message.answer("Заявка не найдена.", reply_markup=back_to_menu_keyboard())
        return

    try:
        price, eta = parse_price_eta(message.text or "")
    except Exception:
        await message.answer("Не понял цену и срок. Формат: `1500; 1 день`", parse_mode="Markdown")
        return

    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            await state.clear()
            await message.answer("Заявка не найдена.", reply_markup=back_to_menu_keyboard())
            return
        master = await get_or_create_staff_user(message, session)
        ticket.master_id = ticket.master_id or master.id
        ticket.final_price = Decimal(price)
        ticket.final_eta = eta
        ticket.status = TicketStatus.PRICE_OFFERED
        client = await session.get(User, ticket.client_id)
        await session.commit()
        await session.refresh(ticket)

    metrics.inc("offers_sent_total")
    await state.clear()
    if client:
        await bot.send_message(client.telegram_id, build_final_offer(ticket), reply_markup=client_final_offer_keyboard(ticket.id))
    await message.answer(
        f"Финальная цена отправлена клиенту по заявке #{ticket.id}.",
        reply_markup=master_ticket_keyboard(ticket.id, assigned_to_me=True, is_admin=is_admin(message.from_user.id)),
    )


@router.message(F.web_app_data)
async def handle_master_webapp_data(message: Message, bot: Bot, state: FSMContext) -> None:
    import json
    from app.db.models import TicketServiceItem
    from app.handlers.client import send_final_offer_to_client

    if not message.from_user or not is_authorized_master(message.from_user.id) or not message.web_app_data:
        return
    try:
        data = json.loads(message.web_app_data.data)
    except Exception:
        await message.answer("Не удалось распарсить данные сметы WebApp.")
        return

    if data.get("action") == "master_webapp_quote":
        state_data = await state.get_data()
        ticket_id = state_data.get("ticket_id")
        items = data.get("items", [])
        total_price = Decimal(str(data.get("total_price", 0)))
        eta = data.get("eta", "1-2 дня")

        if not items or total_price <= 0:
            await message.answer("Смета пуста или имеет нулевую сумму.")
            return

        async with AsyncSessionLocal() as session:
            if not ticket_id:
                ticket = await session.scalar(
                    select(Ticket).where(Ticket.status.in_([TicketStatus.NEW, TicketStatus.ASSIGNED])).order_by(desc(Ticket.id))
                )
                if not ticket:
                    await message.answer("Активная заявка для привязки сметы не найдена.")
                    return
                ticket_id = ticket.id
            else:
                ticket = await session.get(Ticket, ticket_id)

            if not ticket:
                await message.answer("Заявка не найдена.")
                return

            master = await get_or_create_staff_user(message, session)
            ticket.master_id = ticket.master_id or master.id
            ticket.final_price = total_price
            ticket.final_eta = eta
            ticket.status = TicketStatus.PRICE_OFFERED

            for item_data in items:
                title = item_data.get("title", "Работа/деталь")
                price = Decimal(str(item_data.get("price", 0)))
                qty = int(item_data.get("qty", 1))
                line_item = TicketServiceItem(
                    ticket_id=ticket.id,
                    title=title,
                    price=price,
                    qty=qty,
                    source="webapp"
                )
                session.add(line_item)

            client = await session.get(User, ticket.client_id)
            await session.commit()

        metrics.inc("offers_sent_total")
        await state.clear()
        if client:
            await send_final_offer_to_client(bot, ticket, client)
        await message.answer(
            f"✅ Смета из WebApp ({total_price} RUB) успешно сформирована и отправлена клиенту по заявке #{ticket_id}.",
            reply_markup=master_ticket_keyboard(ticket_id, assigned_to_me=True, is_admin=is_admin(message.from_user.id)),
        )


@router.callback_query(F.data.startswith("ticket:stage_menu:"))
async def handle_master_stage_menu(callback: CallbackQuery) -> None:
    if not is_authorized_master(callback.from_user.id):
        await callback.answer("У вас нет прав мастера", show_alert=True)
        return
    ticket_id = int(callback.data.split(":")[2])
    if callback.message:
        await callback.message.edit_text(
            f"📍 Выберите текущий этап ремонта для заявки #{ticket_id}:",
            reply_markup=master_stage_keyboard(ticket_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("ticket:set_stage:"))
async def handle_master_set_stage(callback: CallbackQuery, bot: Bot) -> None:
    if not is_authorized_master(callback.from_user.id):
        await callback.answer("У вас нет прав мастера", show_alert=True)
        return
    parts = callback.data.split(":")
    ticket_id = int(parts[2])
    stage_str = parts[3]

    try:
        new_stage = RepairStage(stage_str)
    except ValueError:
        await callback.answer("Неизвестный этап", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            await callback.answer("Заявка не найдена", show_alert=True)
            return

        ticket.repair_stage = new_stage
        entry = RepairJournalEntry(
            ticket_id=ticket.id,
            stage=new_stage,
            comment=f"Этап изменен на '{STAGE_LABELS.get(new_stage, new_stage.value)}'",
        )
        session.add(entry)
        client = await session.get(User, ticket.client_id)
        await session.commit()

    if client:
        progress_text = render_live_progress_bar(new_stage)
        stage_title = STAGE_LABELS.get(new_stage, new_stage.value)
        try:
            await bot.send_message(
                client.telegram_id,
                f"📍 Обновление по заявке #{ticket_id}:\n"
                f"Новый этап: {stage_title}\n\n"
                f"{progress_text}",
            )
        except Exception:
            pass

    if callback.message:
        await callback.message.edit_text(
            f"✅ Этап заявки #{ticket_id} изменен на '{STAGE_LABELS.get(new_stage, new_stage.value)}'. Клиент уведомлен.",
            reply_markup=master_ticket_keyboard(ticket_id, assigned_to_me=True, is_admin=is_admin(callback.from_user.id)),
        )
    await callback.answer("Этап сохранен")


@router.callback_query(F.data.startswith("ticket:journal_photo_start:"))
async def handle_journal_photo_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_authorized_master(callback.from_user.id):
        await callback.answer("У вас нет прав мастера", show_alert=True)
        return
    ticket_id = int(callback.data.split(":")[2])
    await state.set_state(MasterJournalFSM.waiting_photo)
    await state.update_data(journal_ticket_id=ticket_id)
    if callback.message:
        await callback.message.answer(
            f"📸 Отправьте фото этапа работ по заявке #{ticket_id} (можно с комментарием в подписи к фото)."
        )
    await callback.answer()


@router.message(MasterJournalFSM.waiting_photo, F.photo)
async def handle_journal_photo_upload(message: Message, state: FSMContext, bot: Bot) -> None:
    if not is_authorized_master(message.from_user.id):
        return
    data = await state.get_data()
    ticket_id = data.get("journal_ticket_id")
    if not ticket_id:
        await state.clear()
        return

    photo = message.photo[-1]
    comment = message.caption or "Фотоотчет от мастера"

    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            await message.answer("Заявка не найдена")
            await state.clear()
            return

        entry = RepairJournalEntry(
            ticket_id=ticket.id,
            stage=ticket.repair_stage,
            comment=comment,
            photo_file_id=photo.file_id,
        )
        session.add(entry)
        client = await session.get(User, ticket.client_id)
        await session.commit()

    if client:
        try:
            await bot.send_photo(
                client.telegram_id,
                photo=photo.file_id,
                caption=f"📸 Обновление из мастерской по заявке #{ticket_id}:\n{comment}\n\n{render_live_progress_bar(ticket.repair_stage)}",
            )
        except Exception:
            pass

    await state.clear()
    await message.answer(
        f"✅ Фото этапа успешно сохранено в дневнике работ и отправлено клиенту по заявке #{ticket_id}.",
        reply_markup=master_ticket_keyboard(ticket_id, assigned_to_me=True, is_admin=is_admin(message.from_user.id)),
    )


@router.callback_query(F.data == "admin:schedule")
async def handle_admin_schedule(callback: CallbackQuery) -> None:
    if not is_authorized_master(callback.from_user.id):
        await callback.answer("У вас нет доступа к расписанию", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        masters = (await session.scalars(select(User).where(User.role == UserRole.MASTER))).all()
        if not masters:
            masters = (await session.scalars(select(User).where(User.telegram_id.in_(settings.master_telegram_ids)))).all()

        workloads = []
        for master in masters:
            wl = await get_master_daily_workload(session, master.id)
            wl["master_name"] = master.full_name or (f"Мастер @{master.username}" if master.username else f"Мастер {master.telegram_id}")
            workloads.append(wl)

    card_text = render_master_workload_card(workloads)
    if callback.message:
        await callback.message.edit_text(card_text, reply_markup=admin_schedule_keyboard())
    await callback.answer()


@router.callback_query(F.data == "master:my_schedule")
async def handle_master_my_schedule(callback: CallbackQuery) -> None:
    if not is_authorized_master(callback.from_user.id):
        await callback.answer("У вас нет прав мастера", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        master = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        master_id = master.id if master else None
        wl = await get_master_daily_workload(session, master_id)

    lines = [
        f"📅 Персональное расписание мастера ({wl['date']:%d.%m.%Y}):",
        f"Всего слотов сегодня: {wl['slots_count']}",
        f"Загрузка: {wl['capacity_percent']}% ({wl['total_hours']} ч)",
        "",
    ]
    if wl["slots"]:
        for slot in wl["slots"]:
            status_tag = " [ЗАБЛОКИРОВАНО]" if slot.status == CalendarSlotStatus.BUSY and slot.note else ""
            lines.append(f"• {slot.starts_at:%H:%M}–{slot.ends_at:%H:%M} (Заявка #{slot.ticket_id or 'нет'}){status_tag}")
    else:
        lines.append("Свободный день! Активных записей нет.")

    if callback.message:
        await callback.message.edit_text("\n".join(lines), reply_markup=master_schedule_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:ai_providers")
async def handle_admin_ai_providers(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Только для администраторов", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        providers = (await session.scalars(select(AIProvider))).all()

    lines = [
        "🤖 УПРАВЛЕНИЕ ИИ-ПРОВАЙДЕРАМИ",
        "",
        "В системе зарегистрированы следующие OpenAI-совместимые сервисы:",
        "",
    ]
    if providers:
        for prov in providers:
            default_tag = " [АКТИВЕН ПО УМОЛЧАНИЮ]" if prov.is_default else ""
            lines.append(f"• {prov.name} ({prov.base_url}){default_tag}")
    else:
        lines.append("Кастомные провайдеры в БД не найдены. Используются дефолтные настройки из .env.")

    lines.extend([
        "",
        "💡 Для добавления нового провайдера используйте REST API:",
        "  POST /api/ai/providers",
        "  Body: {\"name\": \"DeepSeek\", \"base_url\": \"https://api.deepseek.com/v1\", \"api_key\": \"...\", \"set_as_default\": true}",
    ])

    if callback.message:
        await callback.message.edit_text("\n".join(lines), reply_markup=admin_ai_providers_keyboard(providers))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:ai_sync:"))
async def handle_admin_ai_sync(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Только для администраторов", show_alert=True)
        return

    provider_id = int(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        try:
            models = await sync_provider_models(session, provider_id)
            await session.commit()
            await callback.answer(f"✅ Автоматически загружено {len(models)} моделей с сервера!", show_alert=True)
        except Exception as exc:
            await callback.answer(f"❌ Ошибка синхронизации: {exc}", show_alert=True)
