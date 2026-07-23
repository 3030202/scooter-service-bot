#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/scooter-service-bot}"

need_root() {
  if [ "$EUID" -ne 0 ]; then
    echo "Запустите скрипт от root: sudo bash deploy.sh"
    exit 1
  fi
}

ask() {
  local var_name="$1"
  local prompt="$2"
  local default="${3:-}"
  local secret="${4:-false}"
  local value=""

  if [ "$secret" = "true" ]; then
    read -r -s -p "$prompt${default:+ [$default]}: " value
    echo
  else
    read -r -p "$prompt${default:+ [$default]}: " value
  fi

  if [ -z "$value" ]; then
    value="$default"
  fi

  printf -v "$var_name" "%s" "$value"
}

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "Docker и Docker Compose уже установлены."
    return
  fi

  echo "Устанавливаю Docker и Docker Compose..."
  apt-get update
  apt-get install -y ca-certificates curl gnupg

  install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
      | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
  fi

  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list

  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

write_env() {
  echo
  echo "Настройка окружения."
  ask BOT_TOKEN "Telegram Bot Token"
  ask AI_API_KEY "AI API Key" "" true
  ask AI_BASE_URL "OpenAI-compatible Base URL" "https://api.openai.com/v1"
  ask AI_TEXT_MODEL "Vision/Text model" "gpt-4o"
  ask AI_TRANSCRIBE_MODEL "Speech-to-text model" "whisper-1"
  ask MASTERS_CHAT_ID "ID чата мастеров" "-1001234567890"
  ask MASTER_TELEGRAM_IDS "Telegram ID мастеров через запятую" ""
  ask ADMIN_TELEGRAM_IDS "Telegram ID админов через запятую" ""
  ask POSTGRES_DB "Postgres DB" "scooter_service"
  ask POSTGRES_USER "Postgres user" "scooter_user"
  ask POSTGRES_PASSWORD "Postgres password" "" true
  ask POSTGRES_PORT "Postgres external port" "5432"
  ask HEALTH_PORT "Bot Health/Metrics Port" "8080"
  ask PROMETHEUS_PORT "Prometheus Port" "9090"

  if [ -z "$BOT_TOKEN" ] || [ -z "$AI_API_KEY" ] || [ -z "$POSTGRES_PASSWORD" ]; then
    echo "BOT_TOKEN, AI_API_KEY и POSTGRES_PASSWORD обязательны."
    exit 1
  fi

  cat > "$PROJECT_DIR/.env" <<ENV
BOT_TOKEN=$BOT_TOKEN
AI_API_KEY=$AI_API_KEY
AI_BASE_URL=$AI_BASE_URL
AI_TEXT_MODEL=$AI_TEXT_MODEL
AI_TRANSCRIBE_MODEL=$AI_TRANSCRIBE_MODEL

MASTERS_CHAT_ID=$MASTERS_CHAT_ID
MASTER_TELEGRAM_IDS=$MASTER_TELEGRAM_IDS
ADMIN_TELEGRAM_IDS=$ADMIN_TELEGRAM_IDS

POSTGRES_DB=$POSTGRES_DB
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_HOST=postgres
POSTGRES_PORT=$POSTGRES_PORT
DATABASE_URL=postgresql+asyncpg://$POSTGRES_USER:$POSTGRES_PASSWORD@postgres:5432/$POSTGRES_DB

REDIS_URL=redis://redis:6379/0
RUN_MIGRATIONS_ON_STARTUP=true

STORAGE_DIR=storage
MEDIA_GROUP_WAIT_SECONDS=2.0
MAX_PHOTOS_PER_TICKET=8
MAX_VOICE_SIZE_MB=20
RATE_LIMIT_PER_MINUTE=20
HEALTH_PORT=$HEALTH_PORT
PROMETHEUS_PORT=$PROMETHEUS_PORT
ENV

  chmod 600 "$PROJECT_DIR/.env"
}

setup_backup_cron() {
  local cron_cmd="0 3 * * * ${PROJECT_DIR}/scripts/backup.sh >> /var/log/scooter_backup.log 2>&1"
  if crontab -l 2>/dev/null | grep -q "scooter-service-bot/scripts/backup.sh"; then
    echo "Backup cron job уже существует."
  else
    echo "Настраиваем ежедневно резервное копирование (3:00 AM)..."
    (crontab -l 2>/dev/null || true; echo "$cron_cmd") | crontab -
  fi
}

main() {
  need_root
  echo "=== Scooter Service Bot interactive deploy ==="

  install_docker

  mkdir -p "$PROJECT_DIR"
  cd "$PROJECT_DIR"

  if [ ! -f "docker-compose.yml" ]; then
    echo "Файлы проекта не найдены в $PROJECT_DIR."
    echo "Скопируйте содержимое архива в $PROJECT_DIR и запустите скрипт снова."
    exit 1
  fi

  if [ -f ".env" ]; then
    read -r -p ".env уже существует. Перезаписать? [y/N]: " rewrite
    if [[ "$rewrite" =~ ^[Yy]$ ]]; then
      write_env
    fi
  else
    write_env
  fi

  if [ -f "scripts/backup.sh" ]; then
    chmod +x scripts/backup.sh
    setup_backup_cron
  fi

  echo "Собираю и запускаю контейнеры..."
  docker compose up --build -d

  echo "Миграции Alembic применяются автоматически при старте bot-контейнера."

  echo
  echo "Готово. Проверка статуса контейнеров:"
  docker compose ps
  echo
  echo "Для просмотра логов: cd $PROJECT_DIR && docker compose logs -f"
}

main "$@"
