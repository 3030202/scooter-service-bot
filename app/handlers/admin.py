from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy import desc, select

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models import CalendarSlot, Ticket, TicketStatus, User, UserRole
from app.keyboards.inline import (
    admin_assign_keyboard,
    admin_queue_keyboard,
    admin_user_role_keyboard,
    admin_users_keyboard,
    main_menu_keyboard,
)

router = Router(name="admin")


def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.admin_telegram_ids


def is_commander_or_admin(telegram_id: int, user_role: UserRole | None = None) -> bool:
    if telegram_id in settings.admin_telegram_ids:
        return True
    if user_role == UserRole.COMMANDER or user_role == UserRole.ADMIN:
        return True
    return False


@router.callback_query(F.data == "admin:users")
@router.message(Command("users"))
async def admin_users_list(event: CallbackQuery | Message) -> None:
    telegram_id = event.from_user.id if event.from_user else 0
    if not is_admin(telegram_id):
        if isinstance(event, CallbackQuery):
            await event.answer("Доступ разрешен только Администраторам", show_alert=True)
        else:
            await event.answer("Доступ разрешен только Администраторам.")
        return

    async with AsyncSessionLocal() as session:
        users = (await session.scalars(select(User).order_by(desc(User.id)))).all()

    text = (
        f"👥 **Управление пользователями и ролями**\n\n"
        f"Всего пользователей в системе: **{len(users)}**\n\n"
        f"Выберите пользователя из списка ниже для просмотра и изменения роли, "
        f"или используйте команду:\n`/setrole <telegram_id> <client|master|commander|admin>`"
    )

    kb = admin_users_keyboard(users)
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(text, reply_markup=kb)
    else:
        await event.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("admin:user_card:"))
async def admin_user_card(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    try:
        user_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Некорректный ID", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        role_titles = {
            UserRole.CLIENT: "👤 Клиент",
            UserRole.MASTER: "👨‍🏭 Мастер",
            UserRole.COMMANDER: "🫡 Командир (Начальник мастерам)",
            UserRole.ADMIN: "🔑 Администратор",
        }
        curr_role_str = role_titles.get(user.role, str(user.role))

        text = (
            f"👤 **Карточка пользователя #{user.id}**\n\n"
            f"💬 **Telegram ID**: `{user.telegram_id}`\n"
            f"👤 **Имя**: {user.full_name or 'Не указано'}\n"
            f"🏷 **Username**: @{user.username or 'нет'}\n"
            f"📱 **Телефон**: {user.phone or 'Не указан'}\n"
            f"🎖 **Текущая роль**: **{curr_role_str}**\n\n"
            f"Выберите новую роль для пользователя ниже:"
        )

        kb = admin_user_role_keyboard(user.id, user.role)
        await callback.answer()
        if callback.message:
            await callback.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("admin:set_role:"))
async def admin_set_user_role(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    try:
        parts = callback.data.split(":")
        user_id = int(parts[2])
        new_role_str = parts[3]
        new_role = UserRole(new_role_str)
    except (IndexError, ValueError):
        await callback.answer("Ошибка параметров роли", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        user.role = new_role
        await session.commit()

        role_titles = {
            UserRole.CLIENT: "👤 Клиент",
            UserRole.MASTER: "👨‍🏭 Мастер",
            UserRole.COMMANDER: "🫡 Командир (Начальник мастерам)",
            UserRole.ADMIN: "🔑 Администратор",
        }
        title = role_titles.get(new_role, new_role.value)

        # Notify target user via bot if possible
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    f"🔔 **Ваш статус и роль в сервисе обновлены!**\n\n"
                    f"Новая роль: **{title}**\n\n"
                    f"Нажмите /start или /menu для загрузки обновлённого меню."
                ),
                reply_markup=main_menu_keyboard(role=new_role),
            )
        except Exception as exc:
            logger.warning("Could not notify user {} about role change: {}", user.telegram_id, exc)

        await callback.answer(f"✅ Роль успешно изменена на {title}", show_alert=True)
        if callback.message:
            text = (
                f"✅ **Роль пользователя #{user.id} ({user.full_name or user.telegram_id}) изменена!**\n\n"
                f"Новая роль: **{title}**"
            )
            kb = admin_user_role_keyboard(user.id, user.role)
            await callback.message.answer(text, reply_markup=kb)


@router.message(Command("setrole"))
async def setrole_command(message: Message, bot: Bot) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("Доступ разрешен только Администраторам.")
        return

    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer(
            "Использование: `/setrole <telegram_id> <client|master|commander|admin>`\n"
            "Пример: `/setrole 189560971 commander`"
        )
        return

    try:
        tg_id = int(parts[1])
        role_str = parts[2].lower()
        new_role = UserRole(role_str)
    except ValueError:
        await message.answer("Неверный Telegram ID или название роли. Допустимо: client, master, commander, admin")
        return

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg_id))
        if not user:
            user = User(telegram_id=tg_id, role=new_role)
            session.add(user)
        else:
            user.role = new_role
        await session.commit()

    try:
        await bot.send_message(
            chat_id=tg_id,
            text=f"🔔 **Ваша роль в сервисе изменена на {new_role.value.upper()}!**\nНажмите /start для обновления меню.",
            reply_markup=main_menu_keyboard(role=new_role),
        )
    except Exception as exc:
        logger.warning("Could not notify user: {}", exc)

    await message.answer(f"✅ Пользователю `{tg_id}` установлена роль **{new_role.value.upper()}**.")


@router.callback_query(F.data == "commander:all_tickets")
@router.callback_query(F.data == "commander:assign_masters")
async def commander_all_tickets(callback: CallbackQuery) -> None:
    telegram_id = callback.from_user.id if callback.from_user else 0
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        user_role = user.role if user else None

        if not is_commander_or_admin(telegram_id, user_role):
            await callback.answer("Доступ разрешён только Командиру или Администратору", show_alert=True)
            return

        tickets = (await session.scalars(select(Ticket).order_by(desc(Ticket.id)).limit(20))).all()

    text = (
        f"🫡 **Панель Командира — Обзор всех заявок сервиса**\n\n"
        f"Всего отображается последних заявок: **{len(tickets)}**\n"
        f"Выберите заявку для просмотра, изменения параметров или назначения мастера:"
    )

    ticket_ids = [t.id for t in tickets]
    kb = admin_queue_keyboard(ticket_ids, filter_name="all")
    await callback.answer()
    if callback.message:
        await callback.message.answer(text, reply_markup=kb)
