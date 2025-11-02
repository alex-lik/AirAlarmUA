"""API роутеры для мониторинга и метрик.

Предоставляет эндпоинты для мониторинга состояния приложения,
сбора Prometheus метрик и отладки.
"""

import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

from utils import metrics_collector, get_logger
from config import settings

# Инициализация логгера
logger = get_logger(__name__)

# Создание роутера
monitoring_router = APIRouter(tags=["monitoring"])


@monitoring_router.get("/metrics", response_class=PlainTextResponse)
async def get_prometheus_metrics() -> str:
    """Получить метрики в формате Prometheus.

    Endpoint экспортирует метрики приложения
    в формате, понятном для Prometheus.

    Returns:
        str: Метрики в формате Prometheus
    """
    try:
        metrics_data = metrics_collector.get_metrics()

        if not metrics_data:
            logger.warning("Пустые метрики")
            return "# No metrics available\n"

        logger.debug("Запрошены Prometheus метрики")
        return metrics_data

    except Exception as e:
        logger.error(f"Ошибка при получении метрик: {e}")
        return f"# Error generating metrics: {e}\n"


@monitoring_router.get("/health/simple")
async def simple_health_check() -> dict:
    """Простая проверка здоровья сервиса.

    Возвращает минимальную информацию о статусе.
    Используется для базовых health checkов.

    Returns:
        dict: Статус сервиса
    """
    return {
        "status": "ok",
        "timestamp": time.time()
    }


@monitoring_router.get("/sentry-debug")
async def trigger_sentry_error():
    """Trigger ошибку для тестирования Sentry.

    Данный эндпоинт используется только для отладки
    и должен быть отключен в production.
    """
    if "production" in settings.cors_origins or settings.cors_origins != ["*"]:
        return {"error": "Debug endpoint disabled in production"}

    logger.warning("Triggered debug error for Sentry")
    raise ValueError("This is a test error for Sentry debugging")


@monitoring_router.get("/info")
async def get_app_info() -> dict:
    """Получить информацию о приложении.

    Возвращает мета-информацию о приложении,
    версии и конфигурации.

    Returns:
        dict: Информация о приложении
    """
    return {
        "app_name": "AirAlarmUA",
        "version": "1.0.0",
        "description": "Система мониторинга воздушных тревог в Украине",
        "features": {
            "telegram_notifications": settings.is_telegram_enabled,
            "sentry_monitoring": settings.is_sentry_enabled,
            "prometheus_metrics": True,
            "rate_limiting": True
        },
        "configuration": {
            "update_interval": settings.update_interval,
            "max_retries": settings.max_retries,
            "api_timeout": settings.request_timeout
        },
        "endpoints": {
            "alerts": "/api/v1/status",
            "regions": "/api/v1/region/{name}",
            "stats": "/api/v1/stats",
            "health": "/api/v1/health",
            "metrics": "/metrics"
        }
    }


@monitoring_router.get("/ping")
async def ping() -> dict:
    """Простой ping endpoint.

    Используется для проверки доступности сервиса.

    Returns:
        dict: Pong ответ
    """
    return {"pong": True, "timestamp": time.time()}