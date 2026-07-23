# Scooter Service Telegram Bot

Асинхронный Telegram-бот для сервисного центра электротранспорта.

## Возможности

- клиентская заявка текстом или голосом;
- запрос телефона клиента перед созданием заявки;
- транскрибация голосовых через OpenAI-compatible API;
- сбор фото и Telegram MediaGroup;
- AI-анализ описания и фотографий;
- клиентское подтверждение заявки перед отправкой мастерам;
- отправка заявки в чат мастеров;
- кнопки мастера: принять, скорректировать, завершить;
- whitelist мастеров и админов через `.env`;
- PostgreSQL + SQLAlchemy + Alembic;
- Redis FSM storage вместо in-memory состояния;
- rate limit и глобальная обработка ошибок;
- Docker Compose.

## Важные настройки `.env`

```env
BOT_TOKEN=123456:telegram_bot_token
MASTERS_CHAT_ID=-1001234567890
MASTER_TELEGRAM_IDS=111111111,222222222
ADMIN_TELEGRAM_IDS=333333333

AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=your_key
AI_TEXT_MODEL=gpt-4o
AI_TRANSCRIBE_MODEL=whisper-1

DATABASE_URL=postgresql+asyncpg://scooter_user:change_me@postgres:5432/scooter_service
REDIS_URL=redis://redis:6379/0
RUN_MIGRATIONS_ON_STARTUP=true

MAX_PHOTOS_PER_TICKET=8
MAX_VOICE_SIZE_MB=20
RATE_LIMIT_PER_MINUTE=20
```

`MASTER_TELEGRAM_IDS` обязателен для production: только эти пользователи смогут нажимать мастерские callback-кнопки.

## Локальный запуск

```bash
cp .env.example .env
# заполните BOT_TOKEN, AI_API_KEY, MASTERS_CHAT_ID, MASTER_TELEGRAM_IDS и POSTGRES_PASSWORD
docker compose up --build -d
docker compose logs -f bot
```

Alembic-миграции запускаются автоматически при старте контейнера `bot`. При необходимости можно отключить это через `RUN_MIGRATIONS_ON_STARTUP=false`.

## Smoke-сценарий перед продом

1. Клиент отправляет `/start`.
2. Клиент отправляет описание текстом или голосом.
3. Бот запрашивает телефон.
4. Клиент отправляет контакт или номер текстом.
5. Клиент отправляет фото.
6. Бот делает AI-анализ и показывает предварительную оценку.
7. Клиент подтверждает заявку.
8. В мастер-чат приходит заявка с кнопками.
9. Авторизованный мастер принимает заявку.
10. Клиент получает уведомление о смене статуса.

## Production notes

Минимально перед публичным запуском проверьте:

- `.env` не попал в git;
- `MASTER_TELEGRAM_IDS` заполнен реальными Telegram ID мастеров;
- база и Redis имеют persistent volumes;
- есть backup `postgres_data` и `storage`;
- бот проходит smoke-сценарий выше.

## Release 1.1: кнопочный workflow заявки

Основной UX теперь построен на inline-кнопках:

- `🛴 Новая заявка`
- `📋 Мои заявки`
- `🔧 Мои работы` для мастеров
- `🧭 Очередь сервиса` для админов

Lifecycle заявки:

```text
draft -> waiting_photos -> ai_analysis -> diagnosed -> new -> assigned -> price_offered -> client_approved -> in_progress -> done
```

Отмена доступна на клиентской стороне и переводит заявку в `cancelled`.

Мастерский сценарий:

1. `🙋 Взять заявку`
2. `💰 AI цена клиенту` или `✏️ Цена/срок`
3. клиент подтверждает финальную цену
4. `▶️ Начать работу`
5. `🏁 Готово`

Для ручного предложения цены формат сообщения мастера:

```text
1500; 1 день
```

Подробности см. в `RELEASE_1_1.md`.


## Release 1.2: Telegram operations layer

Добавлены:

- Telegram-админка с фильтрами очереди;
- назначение мастера кнопками;
- переслотирование заявки кнопками;
- рабочие часы и таймзона сервиса;
- health/readiness/metrics endpoints;
- optional S3/MinIO backend для медиа.

Endpoints observability:

```text
GET /healthz
GET /readyz
GET /metrics
```

По умолчанию медиа остаются локально. Для MinIO/S3 выставьте `STORAGE_BACKEND=s3` и создайте bucket из `S3_BUCKET`.

Подробности см. в `RELEASE_1_2.md`.

## v1.3 Commercial Layer

v1.3 adds the commercial layer on top of the Telegram-first operations flow:

- CRM profile per client (`client_profiles`): repair count, total spent, loyalty tag, last issue summary.
- Service catalog (`service_catalog_items`) with seed positions for battery/BMS, controller, tire/tube, brakes, display/throttle/wiring.
- Ticket line items (`ticket_service_items`) so a master/admin can build a quote from catalog buttons.
- Catalog-driven offer: open a ticket, press `🧾 Каталог/прайс`, add service items, then send the computed total to the client.
- Admin CRM card from the ticket: `👤 CRM клиента`.
- Retention reminders (`retention_reminders`) created automatically when a ticket is marked done.
- Admin retention queue: `🔁 Retention`.
- Client post-repair buttons: review and repeat similar request.

Run migrations as usual:

```bash
alembic upgrade head
```

The catalog is seeded lazily when the admin opens the catalog or a master opens catalog pricing for a ticket. This keeps migration side effects predictable.
