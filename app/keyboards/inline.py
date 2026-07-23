from datetime import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.config import settings
from app.db.models import TicketStatus
from app.services.calendar import format_slot, to_service_time


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить телефон", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_menu_keyboard(is_master: bool = False, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🛴 Новая заявка", callback_data="menu:new_ticket")],
        [InlineKeyboardButton(text="📲 Визуальный выбор поломки (WebApp)", web_app=WebAppInfo(url=f"{settings.webapp_base_url}/webapp/client"))],
        [InlineKeyboardButton(text="📋 Мои заявки", callback_data="menu:my_orders")],
    ]
    if is_master or is_admin:
        rows.append([InlineKeyboardButton(text="🔧 Мои работы", callback_data="menu:my_jobs")])
    if is_admin:
        rows.extend([
            [InlineKeyboardButton(text="🧭 Очередь сервиса", callback_data="admin:queue:all")],
            [InlineKeyboardButton(text="📊 Операционный статус", callback_data="admin:stats")],
            [InlineKeyboardButton(text="📚 Каталог работ", callback_data="admin:catalog")],
            [InlineKeyboardButton(text="🔁 Retention", callback_data="admin:retention")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:home")]])


def client_confirmation_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить мастерам", callback_data=f"client:confirm:{ticket_id}")],
            [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"client:cancel:{ticket_id}")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:home")],
        ]
    )


def client_final_offer_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтверждаю цену", callback_data=f"client:approve_price:{ticket_id}")],
            [InlineKeyboardButton(text="❌ Отказаться", callback_data=f"client:cancel:{ticket_id}")],
            [InlineKeyboardButton(text="📋 Мои заявки", callback_data="menu:my_orders")],
        ]
    )


def client_ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📍 Live-трекинг", callback_data=f"client:track:{ticket_id}"),
                InlineKeyboardButton(text="🚚 Способ получения", callback_data=f"client:pickup_menu:{ticket_id}"),
            ],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"client:cancel:{ticket_id}")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:home")],
        ]
    )


def master_ticket_keyboard(ticket_id: int, assigned_to_me: bool = False, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🙋 Взять заявку", callback_data=f"ticket:assign:{ticket_id}")],
        [
            InlineKeyboardButton(text="💰 AI цена клиенту", callback_data=f"ticket:offer_ai:{ticket_id}"),
            InlineKeyboardButton(text="✏️ Цена/срок", callback_data=f"ticket:edit_offer:{ticket_id}"),
        ],
        [InlineKeyboardButton(text="🧾 Каталог/прайс", callback_data=f"ticket:catalog:{ticket_id}")],
        [InlineKeyboardButton(text="📱 Интерактивная смета (WebApp)", web_app=WebAppInfo(url=f"{settings.webapp_base_url}/webapp/master"))],
        [
            InlineKeyboardButton(text="📍 Сменить этап", callback_data=f"ticket:stage_menu:{ticket_id}"),
            InlineKeyboardButton(text="📸 Фото этапа", callback_data=f"ticket:journal_photo_start:{ticket_id}"),
        ],
        [InlineKeyboardButton(text="▶️ Начать работу", callback_data=f"ticket:start_work:{ticket_id}")],
        [InlineKeyboardButton(text="🏁 Готово", callback_data=f"ticket:done:{ticket_id}")],
    ]
    if is_admin:
        rows.extend([
            [InlineKeyboardButton(text="👤 CRM клиента", callback_data=f"admin:client:{ticket_id}")],
            [InlineKeyboardButton(text="👤 Назначить", callback_data=f"admin:assign_menu:{ticket_id}")],
            [InlineKeyboardButton(text="🕒 Переслотировать", callback_data=f"admin:slot_menu:{ticket_id}")],
            [InlineKeyboardButton(text="🛑 Отменить", callback_data=f"admin:cancel:{ticket_id}")],
            [InlineKeyboardButton(text="🧭 Очередь", callback_data="admin:queue:all")],
        ])
    else:
        rows.append([InlineKeyboardButton(text="🔧 Мои работы", callback_data="menu:my_jobs")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def master_stage_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 1. Принят в сервис", callback_data=f"ticket:set_stage:{ticket_id}:received")],
            [InlineKeyboardButton(text="🔍 2. Диагностика", callback_data=f"ticket:set_stage:{ticket_id}:diagnostics")],
            [InlineKeyboardButton(text="📦 3. Заказ запчастей", callback_data=f"ticket:set_stage:{ticket_id}:parts_ordering")],
            [InlineKeyboardButton(text="🔧 4. Сборка / Пайка", callback_data=f"ticket:set_stage:{ticket_id}:assembly")],
            [InlineKeyboardButton(text="⚡ 5. Тестирование", callback_data=f"ticket:set_stage:{ticket_id}:testing")],
            [InlineKeyboardButton(text="🏁 6. Готов к выдаче", callback_data=f"ticket:set_stage:{ticket_id}:ready")],
            [InlineKeyboardButton(text="⬅️ К заявке", callback_data=f"admin:view:{ticket_id}")],
        ]
    )


def client_pickup_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚶 Самовывоз из сервиса", callback_data=f"client:pickup:{ticket_id}:self_pickup")],
            [InlineKeyboardButton(text="🚚 Доставка курьером", callback_data=f"client:pickup:{ticket_id}:courier")],
            [InlineKeyboardButton(text="⬅️ К заявке", callback_data="menu:my_orders")],
        ]
    )


def admin_queue_keyboard(ticket_ids: list[int], filter_name: str = "all") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"Заявка #{ticket_id}", callback_data=f"admin:view:{ticket_id}")] for ticket_id in ticket_ids]
    rows.extend([
        [
            InlineKeyboardButton(text="🆕 Новые", callback_data="admin:queue:new"),
            InlineKeyboardButton(text="💰 Цена", callback_data="admin:queue:price"),
        ],
        [
            InlineKeyboardButton(text="✅ Подтвержд.", callback_data="admin:queue:approved"),
            InlineKeyboardButton(text="▶️ В работе", callback_data="admin:queue:work"),
        ],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"admin:queue:{filter_name}")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:home")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_assign_keyboard(ticket_id: int, master_telegram_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"Мастер {telegram_id}", callback_data=f"admin:assign:{ticket_id}:{telegram_id}")] for telegram_id in master_telegram_ids]
    rows.append([InlineKeyboardButton(text="⬅️ К заявке", callback_data=f"admin:view:{ticket_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_slot_keyboard(ticket_id: int, slots: list[tuple[datetime, datetime]]) -> InlineKeyboardMarkup:
    rows = []
    for starts_at, ends_at in slots:
        starts_local = to_service_time(starts_at)
        label = f"{starts_local:%d.%m %H:%M}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin:slot:{ticket_id}:{int(starts_at.timestamp())}")])
    rows.append([InlineKeyboardButton(text="⬅️ К заявке", callback_data=f"admin:view:{ticket_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def catalog_items_keyboard(ticket_id: int, items: list) -> InlineKeyboardMarkup:
    rows = []
    for item in items[:10]:
        rows.append([InlineKeyboardButton(text=f"➕ {item.title} — {item.base_price}", callback_data=f"ticket:add_service:{ticket_id}:{item.id}")])
    rows.extend([
        [InlineKeyboardButton(text="💰 Отправить сумму клиенту", callback_data=f"ticket:offer_catalog:{ticket_id}")],
        [InlineKeyboardButton(text="⬅️ К заявке", callback_data=f"admin:view:{ticket_id}")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_catalog_keyboard(items: list) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{item.title} — {item.base_price}", callback_data=f"catalog:view:{item.id}")] for item in items[:15]]
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def client_done_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"client:review:{ticket_id}")],
        [InlineKeyboardButton(text="🔁 Повторить похожую заявку", callback_data=f"client:repeat:{ticket_id}")],
        [InlineKeyboardButton(text="📋 Мои заявки", callback_data="menu:my_orders")],
    ])

def retention_keyboard(reminder_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"Напомнить #{rid}", callback_data=f"retention:send:{rid}")] for rid in reminder_ids[:10]]
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
