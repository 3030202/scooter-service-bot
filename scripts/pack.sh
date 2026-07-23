#!/usr/bin/env bash
set -euo pipefail

# Scooter Service Bot Archive Packer
# Packs project files into scooter-service-bot.tar.gz excluding temporary and build artifacts.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_FILE="${1:-${PROJECT_DIR}/scooter-service-bot.tar.gz}"

echo "📦 Упаковка проекта Scooter Service Bot..."
echo "Путь проекта: ${PROJECT_DIR}"
echo "Выходной архив: ${OUTPUT_FILE}"

cd "${PROJECT_DIR}"

tar --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='.env' \
    --exclude='storage/*' \
    --exclude='*.tar.gz' \
    --exclude='*.zip' \
    --exclude='*:Zone.Identifier' \
    -czf "${OUTPUT_FILE}" .

echo "✅ Архив успешно создан: ${OUTPUT_FILE}"
echo "Для установки скопируйте ${OUTPUT_FILE} и install.sh в директорию /opt на сервере и запустите:"
echo "  sudo bash install.sh"
