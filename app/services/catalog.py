from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select

from app.db.models import ServiceCatalogItem, Ticket, TicketServiceItem

SEED_CATALOG = [
    {
        "code": "battery_diag",
        "title": "Диагностика батареи / BMS",
        "category": "battery",
        "base_price": Decimal("900"),
        "min_price": Decimal("700"),
        "max_price": Decimal("1800"),
        "default_eta": "1-2 дня",
        "keywords": "акб батарея bms заряд зарядка не заряжается просадка выключается",
        "checklist": "Проверить напряжение батареи; Проверить BMS; Проверить зарядное; Проверить просадку под нагрузкой",
    },
    {
        "code": "controller_repair",
        "title": "Диагностика/ремонт контроллера",
        "category": "electronics",
        "base_price": Decimal("1500"),
        "min_price": Decimal("1200"),
        "max_price": Decimal("3500"),
        "default_eta": "1-3 дня",
        "keywords": "контроллер ошибка не едет дергается газ курок мотор колесо",
        "checklist": "Считать ошибку; Проверить фазные провода; Проверить холлы; Проверить MOSFET; Проверить ручку газа",
    },
    {
        "code": "tire_tube",
        "title": "Замена камеры/покрышки",
        "category": "mechanics",
        "base_price": Decimal("600"),
        "min_price": Decimal("500"),
        "max_price": Decimal("1200"),
        "default_eta": "1-2 часа",
        "keywords": "колесо прокол камера покрышка спустило шина резина",
        "checklist": "Осмотреть покрышку; Проверить обод; Заменить камеру; Проверить давление",
    },
    {
        "code": "brake_service",
        "title": "Настройка/ремонт тормозов",
        "category": "brakes",
        "base_price": Decimal("500"),
        "min_price": Decimal("400"),
        "max_price": Decimal("1500"),
        "default_eta": "1-2 часа",
        "keywords": "тормоз тормоза скрип колодки диск ручка не тормозит",
        "checklist": "Проверить колодки; Проверить диск; Настроить калипер; Проверить трос/гидролинию",
    },
    {
        "code": "display_throttle",
        "title": "Дисплей / ручка газа / проводка",
        "category": "electronics",
        "base_price": Decimal("1000"),
        "min_price": Decimal("800"),
        "max_price": Decimal("2500"),
        "default_eta": "1 день",
        "keywords": "дисплей экран курок газ провод проводка включается ошибка",
        "checklist": "Проверить разъемы; Проверить дисплей; Проверить курок газа; Проверить жгут проводки",
    },
]


@dataclass
class CatalogMatch:
    item: ServiceCatalogItem
    score: int


async def seed_catalog(session) -> int:
    created = 0
    for row in SEED_CATALOG:
        existing = await session.scalar(select(ServiceCatalogItem).where(ServiceCatalogItem.code == row["code"]))
        if existing:
            continue
        session.add(ServiceCatalogItem(**row))
        created += 1
    await session.flush()
    return created


async def list_catalog(session, limit: int = 20) -> list[ServiceCatalogItem]:
    return (await session.scalars(
        select(ServiceCatalogItem).where(ServiceCatalogItem.is_active == True).order_by(ServiceCatalogItem.category, ServiceCatalogItem.title).limit(limit)
    )).all()


async def match_catalog(session, text: str, limit: int = 3) -> list[CatalogMatch]:
    await seed_catalog(session)
    normalized = (text or "").lower()
    items = await list_catalog(session, limit=50)
    matches: list[CatalogMatch] = []
    for item in items:
        words = [w.strip().lower() for w in (item.keywords or "").split() if len(w.strip()) >= 3]
        score = sum(1 for word in words if word in normalized)
        if score:
            matches.append(CatalogMatch(item=item, score=score))
    matches.sort(key=lambda x: (x.score, x.item.base_price), reverse=True)
    return matches[:limit]


async def attach_catalog_item(session, ticket: Ticket, item: ServiceCatalogItem, source: str = "catalog") -> TicketServiceItem:
    existing = await session.scalar(
        select(TicketServiceItem).where(TicketServiceItem.ticket_id == ticket.id, TicketServiceItem.catalog_item_id == item.id)
    )
    if existing:
        return existing
    row = TicketServiceItem(
        ticket_id=ticket.id,
        catalog_item_id=item.id,
        title=item.title,
        price=item.base_price,
        qty=1,
        source=source,
    )
    session.add(row)
    await session.flush()
    return row


async def recompute_ticket_price(session, ticket: Ticket) -> Decimal | None:
    rows = (await session.scalars(select(TicketServiceItem).where(TicketServiceItem.ticket_id == ticket.id))).all()
    if not rows:
        return None
    total = sum(Decimal(str(row.price)) * row.qty for row in rows)
    ticket.final_price = total
    if not ticket.final_eta:
        ticket.final_eta = "после диагностики"
    await session.flush()
    return total
