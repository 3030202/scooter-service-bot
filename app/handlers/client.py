import json
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from loguru import logger
from sqlalchemy import desc, select

from app.config import settings
from app.db.models import CalendarSlot, Media, MediaType, Ticket, TicketStatus, User, UserRole
from app.db.session import AsyncSessionLocal
from app.keyboards.inline import (
    back_to_menu_keyboard,
    client_confirmation_keyboard,
    client_final_offer_keyboard,
    client_ticket_keyboard,
    client_done_keyboard,
    contact_keyboard,
    main_menu_keyboard,
    master_ticket_keyboard,
)
from app.services.ai import AIService
from app.services.calendar import format_slot, reserve_next_slot
from app.services.media_group import MediaGroupCollector
from app.services.metrics import metrics
from app.services.storage import media_storage
from app.services.tickets import build_client_preview, build_final_offer, build_ticket_card, status_label

router = Router()
ai_service = AIService()
media_collector = MediaGroupCollector(settings.media_group_wait_seconds)


class TicketFSM(StatesGroup):
    waiting_description = State()
    waiting_contact = State()
    waiting_photos = State()


def is_master_id(telegram_id: int) -> bool:
    return telegram_id in settings.master_telegram_ids or telegram_id in settings.admin_telegram_ids


def is_admin_id(telegram_id: int) -> bool:
    return telegram_id in settings.admin_telegram_ids


async def get_or_create_user(message: Message, session) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
    role = UserRole.ADMIN if is_admin_id(message.from_user.id) else UserRole.MASTER if is_master_id(message.from_user.id) else UserRole.CLIENT
    if user:
        user.username = message.from_user.username
        user.full_name = message.from_user.full_name
        if user.role == UserRole.CLIENT and role != UserRole.CLIENT:
            user.role = role
        return user

    user = User(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def download_file(bot: Bot, file_id: str, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, destination=dst)
    return str(dst)


slot_text = format_slot


async def show_home(message: Message, state: FSMContext | None = None) -> None:
    if state:
        await state.clear()
    telegram_id = message.from_user.id
    await message.answer(
        "Главное меню. Основные действия доступны кнопками.",
        reply_markup=main_menu_keyboard(is_master=is_master_id(telegram_id), is_admin=is_admin_id(telegram_id)),
    )


async def start_ticket_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🛴 Опишите проблему текстом или голосовым. После этого я попрошу телефон и фото поломки.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(TicketFSM.waiting_description)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    async with AsyncSessionLocal() as session:
        await get_or_create_user(message, session)
        await session.commit()
    await show_home(message, state)


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие сброшено.", reply_markup=back_to_menu_keyboard())


@router.message(Command("status"))
async def status(message: Message) -> None:
    await send_my_orders(message)


@router.message(Command("my_orders"))
async def my_orders(message: Message) -> None:
    await send_my_orders(message)


async def send_my_orders(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user:
            await message.answer("Заявок пока нет.", reply_markup=main_menu_keyboard())
            return
        tickets = (await session.scalars(
            select(Ticket).where(Ticket.client_id == user.id).order_by(desc(Ticket.created_at)).limit(5)
        )).all()

    if not tickets:
        await message.answer("Заявок пока нет.", reply_markup=main_menu_keyboard())
        return

    text = "📋 Ваши последние заявки:\n\n" + "\n\n".join(
        f"#{ticket.id} — {status_label(ticket.status)}" for ticket in tickets
    )
    await message.answer(text, reply_markup=main_menu_keyboard(is_master=is_master_id(message.from_user.id), is_admin=is_admin_id(message.from_user.id)))


@router.callback_query(F.data.startswith("menu:"))
async def menu_actions(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":", 1)[1]
    if not callback.message:
        await callback.answer()
        return

    if action == "home":
        await state.clear()
        await callback.message.answer(
            "Главное меню.",
            reply_markup=main_menu_keyboard(is_master=is_master_id(callback.from_user.id), is_admin=is_admin_id(callback.from_user.id)),
        )
        await callback.answer()
        return

    if action == "new_ticket":
        await start_ticket_flow(callback.message, state)
        await callback.answer()
        return

    if action == "my_orders":
        await send_my_orders(callback.message)
        await callback.answer()
        return

    # menu:my_jobs is handled in master.py, but this fallback gives a clean answer when router order changes.
    await callback.answer("Раздел недоступен", show_alert=True)


@router.message(TicketFSM.waiting_description, F.text | F.voice)
async def collect_description(message: Message, state: FSMContext, bot: Bot) -> None:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(message, session)
        text = message.text or ""

        voice_path = None
        if message.voice:
            max_bytes = settings.max_voice_size_mb * 1024 * 1024
            if message.voice.file_size and message.voice.file_size > max_bytes:
                await message.answer(f"Голосовое слишком большое. Лимит: {settings.max_voice_size_mb} MB.")
                return
            voice_path = Path(settings.storage_dir) / "voices" / f"{message.voice.file_unique_id}.ogg"
            await download_file(bot, message.voice.file_id, voice_path)
            text = await ai_service.transcribe_voice(str(voice_path))

        if not text.strip():
            await message.answer("Не получилось получить описание. Отправьте проблему текстом или более четким голосовым.")
            return

        ticket = Ticket(
            client_id=user.id,
            status=TicketStatus.DRAFT,
            description=text.strip(),
            transcript=text.strip() if message.voice else None,
        )
        session.add(ticket)
        await session.flush()

        if message.voice:
            session.add(Media(
                ticket_id=ticket.id,
                type=MediaType.VOICE,
                telegram_file_id=message.voice.file_id,
                telegram_file_unique_id=message.voice.file_unique_id,
                local_path=await media_storage.persist_local_path(str(voice_path), f"voices/{message.voice.file_unique_id}.ogg"),
                mime_type="audio/ogg",
            ))

        await session.commit()
        metrics.inc("tickets_draft_total")
        await state.update_data(ticket_id=ticket.id)

    await message.answer(
        "✅ Описание принято. Теперь отправьте телефон кнопкой ниже или напишите номер сообщением.",
        reply_markup=contact_keyboard(),
    )
    await state.set_state(TicketFSM.waiting_contact)


@router.message(TicketFSM.waiting_contact, F.contact | F.text)
async def collect_contact(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not ticket_id:
        await message.answer("Не нашел активную заявку.", reply_markup=main_menu_keyboard())
        return

    phone = message.contact.phone_number if message.contact else (message.text or "").strip()
    if len(phone) < 5:
        await message.answer("Похоже, это не номер телефона. Отправьте контакт кнопкой или напишите номер.")
        return

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        ticket = await session.get(Ticket, ticket_id)
        if not user or not ticket or ticket.client_id != user.id:
            await message.answer("Заявка не найдена.", reply_markup=main_menu_keyboard())
            return
        user.phone = phone
        ticket.status = TicketStatus.WAITING_PHOTOS
        await session.commit()

    await message.answer(
        f"✅ Телефон сохранен. Теперь отправьте до {settings.max_photos_per_ticket} фото поломки одним сообщением или альбомом.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(TicketFSM.waiting_photos)


@router.message(TicketFSM.waiting_photos, F.photo)
async def collect_photos(message: Message, state: FSMContext, bot: Bot) -> None:
    async def process_album(messages: list[Message]) -> None:
        data = await state.get_data()
        ticket_id = data.get("ticket_id")
        if not ticket_id:
            await message.answer("Не нашел активную заявку.", reply_markup=main_menu_keyboard())
            return

        if len(messages) > settings.max_photos_per_ticket:
            messages = messages[:settings.max_photos_per_ticket]
            await message.answer(f"Принял первые {settings.max_photos_per_ticket} фото, остальные проигнорированы.")

        image_paths: list[str] = []
        reserved_slot = None

        async with AsyncSessionLocal() as session:
            ticket = await session.get(Ticket, ticket_id)
            if not ticket:
                await message.answer("Заявка не найдена.", reply_markup=main_menu_keyboard())
                return

            user = await session.get(User, ticket.client_id)
            if not user or user.telegram_id != message.from_user.id:
                await message.answer("Эта заявка принадлежит другому пользователю.", reply_markup=main_menu_keyboard())
                return

            for msg in messages:
                photo = msg.photo[-1]
                path = Path(settings.storage_dir) / "photos" / str(ticket_id) / f"{photo.file_unique_id}.jpg"
                await download_file(bot, photo.file_id, path)
                image_paths.append(str(path))
                session.add(Media(
                    ticket_id=ticket_id,
                    type=MediaType.PHOTO,
                    telegram_file_id=photo.file_id,
                    telegram_file_unique_id=photo.file_unique_id,
                    local_path=await media_storage.persist_local_path(str(path), f"photos/{ticket_id}/{photo.file_unique_id}.jpg"),
                    mime_type="image/jpeg",
                ))

            ticket.status = TicketStatus.AI_ANALYSIS
            await session.commit()

            await message.answer("🤖 Фото получены. Выполняю предварительную диагностику.")

            from app.services.catalog import attach_catalog_item, list_catalog, seed_catalog
            await seed_catalog(session)
            catalog_items = await list_catalog(session, limit=50)

            result = await ai_service.analyze_ticket(ticket.description or "", image_paths, catalog_items=catalog_items)

            ticket.ai_fault = result.fault
            ticket.ai_price_min = result.price_min
            ticket.ai_price_max = result.price_max
            ticket.ai_eta = result.eta
            ticket.ai_raw_json = result.model_dump_json()
            ticket.status = TicketStatus.DIAGNOSED

            # Auto-attach matched catalog service items
            catalog_map = {item.code: item for item in catalog_items}
            for code in result.matched_catalog_codes:
                if code in catalog_map:
                    await attach_catalog_item(session, ticket, catalog_map[code], source="ai")

            try:
                reserved_slot = await reserve_next_slot(session, ticket.id)
            except Exception as exc:
                logger.warning("Cannot reserve slot: {}", exc)

            await session.commit()
            await session.refresh(ticket)

            preview = build_client_preview(ticket, slot_text(reserved_slot))

        await message.answer(preview, reply_markup=client_confirmation_keyboard(ticket_id))
        await state.clear()

    await media_collector.add(message, process_album)


@router.message(TicketFSM.waiting_photos)
async def waiting_photos_fallback(message: Message) -> None:
    await message.answer("Нужно отправить фото. Для отмены нажмите кнопку в меню или /cancel.")


@router.callback_query(F.data.startswith("client:"))
async def client_ticket_actions(callback: CallbackQuery, bot: Bot) -> None:
    try:
        _, action, ticket_id_raw = callback.data.split(":")
        ticket_id = int(ticket_id_raw)
    except (ValueError, AttributeError):
        await callback.answer("Некорректная команда", show_alert=True)
        return

    notify_masters: str | None = None
    send_final_offer = False

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        ticket = await session.get(Ticket, ticket_id)
        if not user or not ticket or ticket.client_id != user.id:
            await callback.answer("Заявка не найдена", show_alert=True)
            return

        if action == "cancel":
            ticket.status = TicketStatus.CANCELLED
            await session.commit()
            metrics.inc("tickets_cancelled_total")
            notify_masters = f"❌ Клиент отменил заявку #{ticket_id}."
            if callback.message:
                await callback.message.edit_text(f"Заявка #{ticket_id} отменена.")
            await callback.answer("Отменено")
        elif action == "confirm":
            ticket.status = TicketStatus.NEW
            await session.commit()
            metrics.inc("tickets_confirmed_total")
            slot = await session.scalar(
                select(CalendarSlot).where(CalendarSlot.ticket_id == ticket.id).order_by(desc(CalendarSlot.starts_at)).limit(1)
            )
            master_text = build_ticket_card(ticket, user, slot_text(slot))
            notify_masters = master_text
            if callback.message:
                await callback.message.edit_text(f"✅ Заявка #{ticket_id} подтверждена и отправлена мастерам.")
            await callback.answer("Заявка отправлена")
        elif action == "approve_price":
            if ticket.status != TicketStatus.PRICE_OFFERED:
                await callback.answer("Сейчас нет активного предложения цены.", show_alert=True)
                return
            ticket.status = TicketStatus.CLIENT_APPROVED
            await session.commit()
            metrics.inc("prices_approved_total")
            notify_masters = f"✅ Клиент подтвердил цену по заявке #{ticket_id}. Можно начинать работу."
            if callback.message:
                await callback.message.edit_text(f"✅ Цена по заявке #{ticket_id} подтверждена. Мастер получил уведомление.")
            await callback.answer("Подтверждено")
        elif action == "repeat":
            new_ticket = Ticket(
                client_id=user.id,
                status=TicketStatus.DRAFT,
                description=f"Повторная заявка на основе #{ticket.id}: {ticket.description or ticket.ai_fault or 'похожая проблема'}",
                transcript=ticket.transcript,
            )
            session.add(new_ticket)
            await session.flush()
            await session.commit()
            metrics.inc("repeat_tickets_total")
            if callback.message:
                await callback.message.answer(
                    f"🔁 Создал черновик повторной заявки #{new_ticket.id}. Отправьте свежие фото, чтобы обновить диагностику.",
                    reply_markup=client_ticket_keyboard(new_ticket.id),
                )
            await callback.answer("Черновик создан")
        elif action == "review":
            if callback.message:
                await callback.message.answer("⭐ Отзыв пока фиксируется вручную: напишите одним сообщением, что понравилось/что улучшить.")
            await callback.answer()
        else:
            await callback.answer("Неизвестное действие", show_alert=True)
            return

    if notify_masters:
        if action == "confirm":
            await bot.send_message(settings.masters_chat_id, notify_masters, reply_markup=master_ticket_keyboard(ticket_id))
        else:
            await bot.send_message(settings.masters_chat_id, notify_masters)


async def send_final_offer_to_client(bot: Bot, ticket: Ticket, client: User) -> None:
    await bot.send_message(client.telegram_id, build_final_offer(ticket), reply_markup=client_final_offer_keyboard(ticket.id))


@router.message(F.web_app_data)
async def handle_client_webapp_data(message: Message, state: FSMContext) -> None:
    if not message.from_user or not message.web_app_data:
        return
    try:
        data = json.loads(message.web_app_data.data)
    except Exception:
        await message.answer("Не удалось распарсить данные WebApp.")
        return

    if data.get("action") == "client_webapp_select":
        node = data.get("node", "Неизвестный узел")
        details = data.get("details", "")
        description = f"[{node}] {details}".strip()

        async with AsyncSessionLocal() as session:
            user = await get_or_create_user(message, session)
            ticket = Ticket(
                client_id=user.id,
                status=TicketStatus.WAITING_PHOTOS,
                description=description,
            )
            session.add(ticket)
            await session.flush()
            await session.commit()
            ticket_id = ticket.id

        await state.set_state(TicketFSM.waiting_photos)
        await state.update_data(ticket_id=ticket_id)
        await message.answer(
            f"✅ Получены данные WebApp по узлу '{node}'.\n\n"
            f"Создана заявка #{ticket_id}.\n"
            f"Отправьте фотографии самоката для проведения AI-анализа.",
            reply_markup=client_ticket_keyboard(ticket_id)
        )
