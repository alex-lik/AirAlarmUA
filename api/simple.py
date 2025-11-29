"""API роутеры для простых эндпоинтов без префикса.

Предоставляет FastAPI роуты для обратной совместимости
с клиентскими приложениями, которые запрашивают эндпоинты
без префикса /api/v1.
"""

import time
from fastapi import APIRouter
from services import AlertsApiService
from models import AlertSystemStatus, HealthCheckResponse
from utils import metrics_collector, get_logger
from config import settings

# Создание роутера без префикса
simple_router = APIRouter(tags=["simple"])

# Инициализация логгера
logger = get_logger(__name__)

# Глобальная переменная для хранения состояния сервиса
_alerts_service: AlertsApiService = None


def get_alerts_service() -> AlertsApiService:
    """Dependency injection для сервиса API тревог.

    Returns:
        AlertsApiService: Экземпляр сервиса
    """
    global _alerts_service
    if _alerts_service is None:
        _alerts_service = AlertsApiService()
    return _alerts_service


# Глобальная переменная для хранения текущего статуса
_current_status: AlertSystemStatus = None


def get_current_status() -> AlertSystemStatus:
    """Получить текущий статус системы.

    Returns:
        AlertSystemStatus: Текущий статус
    """
    global _current_status
    return _current_status


@simple_router.get("/status")
async def get_status_simple():
    """Получить статусы тревог для всех регионов (без префикса).

    Endpoint для обратной совместимости с клиентами,
    которые запрашивают /status напрямую.
    """
    try:
        # Получаем текущий статус из глобального состояния
        current_status = get_current_status()

        if current_status is None:
            # Если статус еще не загружен, пытаемся получить его
            service = get_alerts_service()
            current_status = await service.get_alerts_status()
            set_current_status(current_status)

        # Формируем ответ в простом формате для обратной совместимости
        response_data = {}
        for region_name, region_status in current_status.regions.items():
            response_data[region_name] = {
                "is_alert": region_status.is_alert,
                "alert_type": region_status.alert_type.value if region_status.alert_type else None,
                "last_updated": region_status.last_updated.isoformat()
            }

        # Добавляем мета-информацию
        response_data["_meta"] = {
            "total_regions": current_status.total_regions,
            "active_alerts": current_status.active_alerts,
            "last_update": current_status.last_update.isoformat(),
            "api_status": current_status.api_status
        }

        logger.info(f"Простой запрос статуса: {current_status.active_alerts} активных из {current_status.total_regions}")

        return response_data

    except Exception as e:
        logger.error(f"Ошибка при получении статуса (простой эндпоинт): {e}")
        return {"error": "Ошибка получения данных"}


@simple_router.get("/health")
async def health_check_simple():
    """Простая проверка здоровья (без префикса).

    Endpoint для обратной совместимости с клиентами,
    которые запрашивают /health напрямую.
    """
    try:
        current_status = get_current_status()
        service = get_alerts_service()

        # Проверяем основные компоненты
        dependencies = {
            "api": current_status.api_status if current_status else "unknown",
            "alerts_service": "ok" if service else "error"
        }

        # Определяем общий статус
        is_healthy = (
            current_status is not None and
            current_status.api_status == "ok" and
            service is not None
        )

        response = HealthCheckResponse(
            status="healthy" if is_healthy else "unhealthy",
            dependencies=dependencies
        )

        # Обновляем метрики
        metrics_collector.update_system_status(is_healthy)

        logger.debug(f"Health check (простой): {response.status}")

        return {
            "status": response.status,
            "dependencies": response.dependencies
        }

    except Exception as e:
        logger.error(f"Ошибка при health check (простой): {e}")
        metrics_collector.update_system_status(False)

        return {
            "status": "unhealthy",
            "dependencies": {"error": str(e)}
        }


def set_current_status(status: AlertSystemStatus) -> None:
    """Установить текущий статус системы.

    Args:
        status: Новый статус системы
    """
    global _current_status
    _current_status = status