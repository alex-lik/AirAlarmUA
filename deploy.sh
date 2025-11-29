#!/bin/bash

# Скрипт деплоя для AirAlarmUA API
# Не перезаписывает существующий .env файл

set -e

echo "=== ДЕПЛОЙ AirAlarmUA API ==="

# Проверяем, что мы находимся в нужной директории
if [ ! -f "main.py" ]; then
    echo "Ошибка: main.py не найден. Убедитесь, что вы находитесь в корневой директории проекта."
    exit 1
fi

# Создаем .env файл только если его нет
if [ ! -f .env ]; then
    echo "Создание .env файла из шаблона..."
    # Создаем минимальный .env файл с необходимыми переменными
    cat > .env << EOF
# AirAlarmUA API Configuration
# Сгенерировано автоматически при первом деплое

# Основные настройки
ENVIRONMENT=production
LOG_LEVEL=INFO
PORT=8000

# Rate limiting
RATE_LIMIT=100/minute

# API настройки
UPDATE_INTERVAL=30
REQUEST_TIMEOUT=10
MAX_RETRIES=3

# CORS
CORS_ORIGINS=["*"]

# Метрики
IS_PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9091

# Telegram (установите свои значения)
# TELEGRAM_BOT_TOKEN=ваш_токен_бота
# TELEGRAM_CHAT_IDS=id1,id2,id3
# IS_TELEGRAM_ENABLED=true

# Sentry (установите свои значения)
# SENTRY_DSN=ваш_sentry_dsn
# IS_SENTRY_ENABLED=true
EOF
    echo "Файл .env создан. Обязательно настройте переменные окружения перед запуском."
else
    echo "Файл .env уже существует, не перезаписываем."
fi

# Останавливаем существующий контейнер если есть
echo "Остановка существующих контейнеров..."
docker-compose -f docker-compose.prod.yml down || true

# Собираем образ
echo "Сборка Docker образа..."
docker-compose -f docker-compose.prod.yml build --no-cache

# Запускаем сервис
echo "Запуск сервиса..."
docker-compose -f docker-compose.prod.yml up -d

# Проверяем статус
echo "Проверка статуса..."
sleep 10
docker-compose -f docker-compose.prod.yml ps

# Проверяем healthcheck
echo "Проверка доступности сервиса..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Сервис успешно запущен и доступен!"
        break
    else
        echo "Попытка $attempt/$max_attempts: сервис еще не доступен..."
        sleep 5
        attempt=$((attempt + 1))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ Сервис не стал доступным за отведенное время. Проверьте логи:"
    docker-compose -f docker-compose.prod.yml logs
    exit 1
fi

# Показываем логи
echo "=== Последние логи ==="
docker-compose -f docker-compose.prod.yml logs --tail=20

echo ""
echo "=== ДЕПЛОЙ ЗАВЕРШЕН ==="
echo "API доступен по адресу: http://localhost:8000"
echo "Документация: http://localhost:8000/docs"
echo "Статус: docker-compose -f docker-compose.prod.yml ps"