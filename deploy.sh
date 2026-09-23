#!/bin/bash
# Deploy script for AirAlarmUA API.
# Does not overwrite an existing .env file.

set -e

echo "=== Deploy AirAlarmUA API ==="

if [ ! -f "main.py" ]; then
    echo "Error: main.py not found. Run from the project root."
    exit 1
fi

if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "Created .env. Set ALERTS_API_TOKEN / TELEGRAM_TOKEN before running."
else
    echo ".env already exists, keeping it."
fi

echo "Stopping existing containers..."
docker compose -f docker-compose.prod.yml down || true

echo "Building image..."
docker compose -f docker-compose.prod.yml build --no-cache

echo "Starting service..."
docker compose -f docker-compose.prod.yml up -d

echo "Checking status..."
sleep 10
docker compose -f docker-compose.prod.yml ps

echo "Waiting for service..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "Service is up."
        break
    else
        echo "Attempt $attempt/$max_attempts: not ready yet..."
        sleep 5
        attempt=$((attempt + 1))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    echo "Service did not become ready in time. Logs:"
    docker compose -f docker-compose.prod.yml logs
    exit 1
fi

echo "=== Recent logs ==="
docker compose -f docker-compose.prod.yml logs --tail=20

echo ""
echo "=== Deploy done ==="
echo "API: http://localhost:8000"
echo "Docs: http://localhost:8000/docs"
