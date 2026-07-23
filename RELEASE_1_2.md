# Release 1.2: Telegram operations layer

Цель релиза: превратить v1.1 из кнопочного workflow в управляемую сервисную систему внутри Telegram.

## Что добавлено

### Админка внутри Telegram

- `📊 Операционный статус` в главном меню админа.
- Очередь с фильтрами:
  - новые / назначенные;
  - ожидают подтверждения цены;
  - клиент подтвердил;
  - в работе.
- Карточка заявки с админскими действиями:
  - назначить мастера;
  - переслотировать;
  - отменить;
  - изменить цену/срок через существующий мастерский flow.

### Назначение мастера

Админ может назначить заявку конкретному мастеру из `MASTER_TELEGRAM_IDS` кнопками. Если мастер еще не писал боту, его технический user создается автоматически по Telegram ID.

### Календарь / слоты

- Рабочие часы через `.env`:
  - `SERVICE_TIMEZONE`
  - `WORKDAY_START_HOUR`
  - `WORKDAY_END_HOUR`
  - `WORKDAY_NUMBERS`
  - `SLOT_DURATION_MINUTES`
  - `SLOT_SEARCH_DAYS`
- Слоты теперь ищутся только в рабочем окне.
- Проверяется пересечение слотов.
- При старте работы слот переводится в `busy`.
- При завершении заявки слот переводится в `done`.
- При отмене слот переводится в `cancelled`.

### Observability

Добавлен lightweight HTTP server:

- `/healthz` — процесс жив;
- `/readyz` — проверка подключения к БД;
- `/metrics` — Prometheus-compatible counters.

Порт по умолчанию: `8080`.

### S3 / MinIO контур

- Добавлен optional storage backend `local|s3`.
- В `docker-compose.yml` добавлен MinIO.
- По умолчанию включен `local`, чтобы не усложнять запуск.
- Для S3/MinIO нужно выставить `STORAGE_BACKEND=s3` и S3-переменные.

## Новые counters

- `tickets_draft_total`
- `tickets_confirmed_total`
- `tickets_cancelled_total`
- `prices_approved_total`
- `master_assignments_total`
- `admin_assignments_total`
- `offers_sent_total`
- `work_started_total`
- `tickets_done_total`
- `errors_total`
- `rate_limited_total`

## Smoke test v1.2

1. Админ открывает `/start`.
2. Нажимает `📊 Операционный статус`.
3. Клиент создает заявку.
4. Админ открывает `🧭 Очередь сервиса`.
5. Админ открывает карточку заявки.
6. Админ назначает мастера кнопкой.
7. Админ переслотирует заявку кнопкой.
8. Мастер отправляет цену клиенту.
9. Клиент подтверждает цену.
10. Мастер начинает работу.
11. Мастер завершает заявку.
12. Проверить `/metrics`.

## Ограничения

- Это все еще Telegram-first админка, не web CRM.
- Каталог работ и прайс-движок не включены в v1.2 — это v1.3.
- S3 bucket auto-create не добавлен: bucket нужно создать в MinIO/S3 заранее.
