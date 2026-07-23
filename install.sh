#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Scooter Service Telegram Bot — Interactive Production Installer
# ==============================================================================

# Formatting & Colors
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

TARGET_DIR="/opt/scooter-service-bot"

print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "=============================================================================="
    echo "       🛴 ИНТЕРАКТИВНЫЙ МАСТЕР УСТАНОВКИ SCOOTER SERVICE BOT V1.6             "
    echo "=============================================================================="
    echo -e "${NC}"
}

need_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}${BOLD}[ОШИБКА]${NC} Для установки требуются права суперпользователя (root)."
        echo -e "Запустите скрипт через sudo:"
        echo -e "  ${YELLOW}sudo bash install.sh${NC}"
        exit 1
    fi
}

log_info() {
    echo -e "${BLUE}[ИНФО]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[УСПЕХ]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[ВНИМАНИЕ]${NC} $1"
}

log_error() {
    echo -e "${RED}[ОШИБКА]${NC} $1"
}

print_hint() {
    echo -e "  ${YELLOW}💡 Подсказка:${NC} $1"
}

# Function to ask interactive questions with hints & validation
ask_input() {
    local var_name="$1"
    local title="$2"
    local hint="$3"
    local default_val="${4:-}"
    local is_secret="${5:-false}"
    local required="${6:-false}"

    echo
    echo -e "${BOLD}${CYAN}▶ $title${NC}"
    if [ -n "$hint" ]; then
        print_hint "$hint"
    fi

    local user_val=""
    while true; do
        if [ "$is_secret" = "true" ]; then
            read -r -s -p "Ввод${default_val:+ [по умолчанию: $default_val]}: " user_val
            echo
        else
            read -r -p "Ввод${default_val:+ [по умолчанию: $default_val]}: " user_val
        fi

        if [ -z "$user_val" ]; then
            user_val="$default_val"
        fi

        if [ "$required" = "true" ] && [ -z "$user_val" ]; then
            log_warn "Это поле обязательно для заполнения. Пожалуйста, введите значение."
            continue
        fi

        break
    done

    printf -v "$var_name" "%s" "$user_val"
}

# Unpack archive if present
unpack_archive_if_needed() {
    log_info "Проверка файлов проекта в ${TARGET_DIR}..."

    mkdir -p "${TARGET_DIR}"

    # If docker-compose.yml already exists in TARGET_DIR, we are ready
    if [ -f "${TARGET_DIR}/docker-compose.yml" ]; then
        log_success "Файлы проекта обнаружены в ${TARGET_DIR}."
        cd "${TARGET_DIR}"
        return
    fi

    # Find archive in current directory or /opt
    local archive=""
    for candidate in "scooter-service-bot.tar.gz" "*.tar.gz" "*.tgz" "*.zip"; do
        for loc in "." "/opt" ".."; do
            matches=(${loc}/${candidate})
            if [ -f "${matches[0]}" ]; then
                archive="${matches[0]}"
                break 2
            fi
        done
    done

    if [ -n "$archive" ] && [ -f "$archive" ]; then
        log_info "Найден архив проекта: ${archive}. Распаковка в ${TARGET_DIR}..."
        if [[ "$archive" == *.zip ]]; then
            unzip -q -o "$archive" -d "${TARGET_DIR}"
        else
            tar -xzf "$archive" -C "${TARGET_DIR}"
        fi
        log_success "Архив успешно распакован в ${TARGET_DIR}."
        cd "${TARGET_DIR}"
    else
        log_error "Файлы проекта или архив не найдены!"
        echo "Поместите архив проекта (scooter-service-bot.tar.gz) и install.sh в директорию /opt и запустите:"
        echo "  sudo bash install.sh"
        exit 1
    fi
}

# Install missing system dependencies & Docker
install_dependencies() {
    log_info "Проверка системных зависимостей (Docker, Docker Compose, Curl)..."

    # Detect package manager
    local pkg_manager=""
    if command -v apt-get >/dev/null 2>&1; then
        pkg_manager="apt"
    elif command -v dnf >/dev/null 2>&1; then
        pkg_manager="dnf"
    elif command -v yum >/dev/null 2>&1; then
        pkg_manager="yum"
    fi

    # Install basic utils if missing
    if ! command -v curl >/dev/null 2>&1 || ! command -v tar >/dev/null 2>&1 || ! command -v gzip >/dev/null 2>&1; then
        log_info "Установка базовых утилит (curl, tar, gzip)..."
        if [ "$pkg_manager" = "apt" ]; then
            apt-get update -qq && apt-get install -y -qq curl tar gzip ca-certificates gnupg
        elif [ "$pkg_manager" = "dnf" ] || [ "$pkg_manager" = "yum" ]; then
            $pkg_manager install -y curl tar gzip ca-certificates gnupg
        fi
    fi

    # Check Docker
    if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
        log_warn "Docker или Docker Compose не обнаружены. Начинаем автоматическую установку..."
        if [ "$pkg_manager" = "apt" ]; then
            apt-get update -qq
            apt-get install -y -qq ca-certificates curl gnupg
            install -m 0755 -d /etc/apt/keyrings
            if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
                curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
                chmod a+r /etc/apt/keyrings/docker.gpg
            fi
            . /etc/os-release
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME:-noble} stable" > /etc/apt/sources.list.d/docker.list
            apt-get update -qq
            apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        elif [ "$pkg_manager" = "dnf" ] || [ "$pkg_manager" = "yum" ]; then
            curl -fsSL https://get.docker.com | sh
        else
            log_error "Не удалось определить пакетный менеджер. Установите Docker вручную."
            exit 1
        fi
        log_success "Docker и Docker Compose успешно установлены."
    else
        log_success "Docker и Docker Compose установлены и готовы к работе."
    fi

    # Ensure docker daemon is running
    if command -v systemctl >/dev/null 2>&1; then
        systemctl enable docker >/dev/null 2>&1 || true
        systemctl start docker >/dev/null 2>&1 || true
    fi
}

generate_random_password() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 12
    else
        tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24 || echo "scooter_secure_pass_$(date +%s)"
    fi
}

collect_configuration() {
    echo -e "\n${BOLD}${CYAN}=============================================================================="
    echo "              ⚙️ НАСТРОЙКА КОНФИГУРАЦИИ ОКРУЖЕНИЯ (.env)                      "
    echo -e "==============================================================================${NC}"

    if [ -f ".env" ]; then
        log_warn "Найден существующий файл конфигурации .env."
        read -r -p "Желаете перенастроить .env заново? [y/N]: " reconfigure
        if [[ ! "$reconfigure" =~ ^[Yy]$ ]]; then
            log_info "Используем существующий файл .env."
            return
        fi
    fi

    ask_input BOT_TOKEN "Telegram Bot Token" \
        "Токен бота, полученный у @BotFather в Telegram (например: 123456789:ABCdefGHI...)" \
        "" false true

    ask_input MASTERS_CHAT_ID "ID чата мастеров" \
        "Telegram ID группы/канала мастеров для уведомлений о заявках (обычно начинается с -100...)" \
        "-1001234567890" false true

    ask_input MASTER_TELEGRAM_IDS "Telegram ID мастеров (Whitelist)" \
        "Список Telegram ID мастеров через запятую (например: 111111111,222222222). Узнать ID: @userinfobot" \
        "" false true

    ask_input ADMIN_TELEGRAM_IDS "Telegram ID администраторов" \
        "Список Telegram ID администраторов через запятую" \
        "" false false

    ask_input AI_API_KEY "AI API Key" \
        "Ключ API для OpenAI или совместимого сервиса (GPT-4o & Whisper)" \
        "" true true

    ask_input AI_BASE_URL "AI Base URL" \
        "Адрес API провайдера AI" \
        "https://api.openai.com/v1" false false

    ask_input AI_TEXT_MODEL "AI Модель Диагностики" \
        "Модель OpenAI для текстового и визуального анализа" \
        "gpt-4o" false false

    ask_input POSTGRES_PASSWORD "Пароль базы данных PostgreSQL" \
        "Оставьте пустым для автоматической генерации надежного случайного пароля" \
        "" true false

    if [ -z "$POSTGRES_PASSWORD" ]; then
        POSTGRES_PASSWORD="$(generate_random_password)"
        log_info "Сгенерирован случайный пароль БД PostgreSQL."
    fi

    ask_input WEBAPP_BASE_URL "Base URL для WebApp" \
        "URL для работы Telegram Mini App WebApp (например: http://localhost:8080 или https://bot.example.com)" \
        "http://localhost:8080" false false

    # Save .env file
    cat > "${TARGET_DIR}/.env" <<EOF
# Scooter Service Bot Production Environment
BOT_TOKEN=${BOT_TOKEN}
MASTERS_CHAT_ID=${MASTERS_CHAT_ID}
MASTER_TELEGRAM_IDS=${MASTER_TELEGRAM_IDS}
ADMIN_TELEGRAM_IDS=${ADMIN_TELEGRAM_IDS}

AI_API_KEY=${AI_API_KEY}
AI_BASE_URL=${AI_BASE_URL}
AI_TEXT_MODEL=${AI_TEXT_MODEL}
AI_TRANSCRIBE_MODEL=whisper-1

POSTGRES_DB=scooter_service
POSTGRES_USER=scooter_user
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://scooter_user:${POSTGRES_PASSWORD}@postgres:5432/scooter_service

REDIS_URL=redis://redis:6379/0
RUN_MIGRATIONS_ON_STARTUP=true

STORAGE_DIR=storage
STORAGE_BACKEND=local
MEDIA_GROUP_WAIT_SECONDS=2.0
MAX_PHOTOS_PER_TICKET=8
MAX_VOICE_SIZE_MB=20
RATE_LIMIT_PER_MINUTE=20

SERVICE_TIMEZONE=Europe/Bucharest
WORKDAY_START_HOUR=10
WORKDAY_END_HOUR=19
SLOT_DURATION_MINUTES=120

RETENTION_AUTO_SEND_ENABLED=true
RETENTION_CHECK_INTERVAL_SECONDS=60
RETENTION_BATCH_SIZE=20

WEBAPP_BASE_URL=${WEBAPP_BASE_URL}

OBSERVABILITY_ENABLED=true
HEALTH_HOST=0.0.0.0
HEALTH_PORT=8080
PROMETHEUS_PORT=9090
EOF

    chmod 600 "${TARGET_DIR}/.env"
    log_success "Файл конфигурации ${TARGET_DIR}/.env создан и защищен (chmod 600)."
}

setup_backup_cron() {
    if [ -f "${TARGET_DIR}/scripts/backup.sh" ]; then
        chmod +x "${TARGET_DIR}/scripts/backup.sh"
        local cron_cmd="0 3 * * * ${TARGET_DIR}/scripts/backup.sh >> /var/log/scooter_backup.log 2>&1"
        if ! crontab -l 2>/dev/null | grep -q "scooter-service-bot/scripts/backup.sh"; then
            log_info "Настройка ежедневного автоматического резервного копирования БД и медиа (3:00 AM)..."
            (crontab -l 2>/dev/null || true; echo "$cron_cmd") | crontab -
            log_success "Задание backup cron успешно добавлено."
        fi
    fi
}

deploy_containers() {
    echo -e "\n${BOLD}${CYAN}=============================================================================="
    echo "                  🐳 СБОРКА И ЗАПУСК DOCKER-КОНТЕЙНЕРОВ                       "
    echo -e "==============================================================================${NC}"

    log_info "Выполняется сборка и запуск сервисов (Bot, PostgreSQL, Redis, Prometheus)..."
    docker compose up --build -d

    log_info "Ожидание инициализации и выполнения авто-миграций Alembic (10 сек)..."
    sleep 10

    log_info "Проверка работоспособности сервиса (/healthz)..."
    local retries=6
    local healthy=false
    while [ $retries -gt 0 ]; do
        if curl -s -f http://localhost:8080/healthz >/dev/null 2>&1; then
            healthy=true
            break
        fi
        sleep 3
        ((retries--))
    done

    if [ "$healthy" = "true" ]; then
        log_success "Сервис успешно запущен и прошел проверку Healthcheck! (HTTP 200 OK)"
    else
        log_warn "Контейнер запущен, но /healthz еще не ответил. Проверьте логи: docker compose logs -f"
    fi
}

print_summary() {
    echo -e "\n${BOLD}${GREEN}=============================================================================="
    echo "               🎉 УСТАНОВКА И ЗАПУСК УСПЕШНО ЗАВЕРШЕНЫ!                       "
    echo -e "==============================================================================${NC}"
    echo
    echo -e "${BOLD}Статус сервисов:${NC}"
    docker compose ps
    echo
    echo -e "${BOLD}Полезные ссылки и эндпоинты:${NC}"
    echo -e "  • Healthcheck: ${CYAN}http://localhost:8080/healthz${NC}"
    echo -e "  • Metrics:     ${CYAN}http://localhost:8080/metrics${NC}"
    echo -e "  • Prometheus:  ${CYAN}http://localhost:9090${NC}"
    echo -e "  • WebApp URL:   ${CYAN}${WEBAPP_BASE_URL:-http://localhost:8080}${NC}"
    echo
    echo -e "${BOLD}Команды управления:${NC}"
    echo -e "  • Просмотр логов:       ${YELLOW}cd ${TARGET_DIR} && docker compose logs -f${NC}"
    echo -e "  • Перезапуск бота:      ${YELLOW}cd ${TARGET_DIR} && docker compose restart bot${NC}"
    echo -e "  • Остановка сервисов:   ${YELLOW}cd ${TARGET_DIR} && docker compose down${NC}"
    echo -e "  • Ручной бэкап:         ${YELLOW}${TARGET_DIR}/scripts/backup.sh${NC}"
    echo
}

main() {
    print_banner
    need_root
    unpack_archive_if_needed
    install_dependencies
    collect_configuration
    setup_backup_cron
    deploy_containers
    print_summary
}

main "$@"
