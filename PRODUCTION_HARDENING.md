# Production Hardening & Deployment Changelog

## Сделано

1. **Whitelist мастеров**
   - Добавлены `MASTER_TELEGRAM_IDS` и `ADMIN_TELEGRAM_IDS`.
   - Callback-действия мастера доступны только авторизованным Telegram ID.

2. **Redis FSM Storage**
   - `MemoryStorage` заменен на `RedisStorage`.
   - В `docker-compose.yml` добавлен Redis с persistent volume.

3. **Global Error Middleware**
   - Добавлен `ErrorMiddleware`.
   - Необработанные ошибки логируются и не пробрасывают пользователю traceback.

4. **Rate Limit**
   - Добавлен `RateLimitMiddleware`.
   - Настройка: `RATE_LIMIT_PER_MINUTE`.

5. **Автомиграции**
   - При старте bot-контейнера выполняется `alembic upgrade head`.
   - Настройка: `RUN_MIGRATIONS_ON_STARTUP`.

6. **Клиентское подтверждение заявки**
   - Клиент сначала отправляет описание -> телефон -> фото.
   - После AI-анализа клиент подтверждает или отменяет заявку.

7. **Многоэтапный Dockerfile & Безопасность (Hardening)**
   - Выполнен перерелиз Dockerfile с multi-stage сборкой (builder/runtime).
   - Приложение запускается от не привилегированного пользователя `appuser` (UID 10001).
   - Добавлен `.dockerignore` для исключения служебных файлов из образа.
   - Настроен встроенный Docker Healthcheck (`http://localhost:8080/healthz`).

8. **CI/CD Автоматизация**
   - Настроен GitHub Actions workflow (`.github/workflows/ci-cd.yml`).
   - Автоматическая проверка синтаксиса, запуск `pytest` и тестовая сборка Docker при PR/Push.
   - Деплой по SSH на продакшн-сервер при пуше в ветку `main`.

9. **Резервное копирование (Backups)**
   - Создан скрипт `scripts/backup.sh` для бэкапа PostgreSQL (`pg_dump` + `gzip`) и `storage/`.
   - Реализована ротация копий (7 ежедневных, 4 еженедельных).
   - В `deploy.sh` добавлена авто-настройка `cron` задания.

10. **Мониторинг и Метрики**
    - Добавлен контейнер Prometheus (`monitoring/prometheus.yml`).
    - Мониторинг ендпоинтов `/healthz`, `/readyz`, `/metrics` (Prometheus format).

## Что проверить перед запуском

- Заполнить реальные `MASTER_TELEGRAM_IDS` и `ADMIN_TELEGRAM_IDS` в `.env`.
- Проверить секреты в GitHub Repository: `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`.
- Убедиться, что `cron` или `systemd-timer` выполняют `scripts/backup.sh`.
- Проверить доступность метрик по `http://<host>:8080/metrics` и интерфейса Prometheus на `http://<host>:9090`.
