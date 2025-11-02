"""API роутеры для эндпоинтов статуса тревог.

Предоставляет FastAPI роутеры для получения информации
о воздушных тревогах в различных регионах Украины.
"""

import time
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import APIRouter, Request, HTTPException, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

from services import AlertsApiService
from models import AlertSystemStatus, HealthCheckResponse
from utils import metrics_collector, get_logger
from config import settings

# Инициализация логгера
logger = get_logger(__name__)

# Инициализация limiter
limiter = Limiter(key_func=get_remote_address)

# Создание роутера
alerts_router = APIRouter(prefix="/api/v1", tags=["alerts"])

# Глобальная переменная для хранения состояния сервиса
_alerts_service: Optional[AlertsApiService] = None


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
_current_status: Optional[AlertSystemStatus] = None


def get_current_status() -> Optional[AlertSystemStatus]:
    """Получить текущий статус системы.

    Returns:
        Optional[AlertSystemStatus]: Текущий статус или None
    """
    global _current_status
    return _current_status


def set_current_status(status: AlertSystemStatus) -> None:
    """Установить текущий статус системы.

    Args:
        status: Новый статус системы
    """
    global _current_status
    _current_status = status


@alerts_router.get("/status")
@limiter.limit(settings.rate_limit)
async def get_all_alerts_status(request: Request) -> Dict:
    """Получить статусы тревог для всех регионов.

    Endpoint возвращает текущие статусы воздушных тревог
    для всех регионов Украины.

    Args:
        request: FastAPI Request объект

    Returns:
        Dict: Словарь с статусами регионов

    Raises:
        HTTPException: При ошибках получения данных
    """
    start_time = time.time()

    try:
        # Получаем текущий статус из глобального состояния
        current_status = get_current_status()

        if current_status is None:
            # Если статус еще не загружен, пытаемся получить его
            service = get_alerts_service()
            current_status = await service.get_alerts_status()

        # Формируем ответ
        response_data = {}
        for region_name, region_status in current_status.regions.items():
            response_data[region_name] = {
                "is_alert": region_status.is_alert,
                "alert_type": region_status.alert_type.value,
                "last_updated": region_status.last_updated.isoformat()
            }

        # Добавляем мета-информацию
        response_data["_meta"] = {
            "total_regions": current_status.total_regions,
            "active_alerts": current_status.active_alerts,
            "last_update": current_status.last_update.isoformat(),
            "api_status": current_status.api_status
        }

        # Записываем метрики
        duration = time.time() - start_time
        metrics_collector.record_http_request(
            method="GET",
            endpoint="/status",
            status_code=200,
            duration=duration
        )

        logger.info(f"Запрос статуса тревог: {current_status.active_alerts} активных из {current_status.total_regions}")

        return response_data

    except Exception as e:
        duration = time.time() - start_time
        metrics_collector.record_http_request(
            method="GET",
            endpoint="/status",
            status_code=500,
            duration=duration
        )

        logger.error(f"Ошибка при получении статуса тревог: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения данных о тревогах")


@alerts_router.get("/region/{region_name}")
@limiter.limit(settings.rate_limit)
async def get_region_alerts_status(
    request: Request,
    region_name: str,
    service: AlertsApiService = Depends(get_alerts_service)
) -> Dict:
    """Получить статусы тревог для конкретного региона.

    Ищет регионы по подстроке в названии. Возвращает все совпадения.

    Args:
        request: FastAPI Request объект
        region_name: Название или часть названия региона
        service: Сервис API тревог

    Returns:
        Dict: Найденные регионы и их статусы

    Raises:
        HTTPException: Если регион не найден
    """
    start_time = time.time()

    try:
        # Получаем данные о регионе
        found_regions = await service.get_region_status(region_name)

        if not found_regions:
            duration = time.time() - start_time
            metrics_collector.record_http_request(
                method="GET",
                endpoint=f"/region/{region_name}",
                status_code=404,
                duration=duration
            )

            logger.warning(f"Регион не найден: {region_name}")
            raise HTTPException(status_code=404, detail="Регион не найден")

        # Формируем ответ с дополнительной информацией
        response_data = {}
        for region, is_alert in found_regions.items():
            response_data[region] = {
                "is_alert": is_alert,
                "search_match": region_name.lower() in region.lower()
            }

        # Добавляем мета-информацию
        response_data["_meta"] = {
            "search_query": region_name,
            "found_count": len(found_regions)
        }

        # Записываем метрики
        duration = time.time() - start_time
        metrics_collector.record_http_request(
            method="GET",
            endpoint=f"/region/{region_name}",
            status_code=200,
            duration=duration
        )

        logger.info(f"Поиск региона '{region_name}': найдено {len(found_regions)} совпадений")

        return response_data

    except HTTPException:
        raise

    except Exception as e:
        duration = time.time() - start_time
        metrics_collector.record_http_request(
            method="GET",
            endpoint=f"/region/{region_name}",
            status_code=500,
            duration=duration
        )

        logger.error(f"Ошибка при поиске региона '{region_name}': {e}")
        raise HTTPException(status_code=500, detail="Ошибка при поиске региона")


@alerts_router.get("/health")
async def health_check() -> HealthCheckResponse:
    """Проверить здоровье сервиса.

    Возвращает информацию о статусе работы приложения
    и его зависимостей.

    Returns:
        HealthCheckResponse: Статус здоровья сервиса
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

        logger.debug(f"Health check: {response.status}")

        return response

    except Exception as e:
        logger.error(f"Ошибка при health check: {e}")
        metrics_collector.update_system_status(False)

        return HealthCheckResponse(
            status="unhealthy",
            dependencies={"error": str(e)}
        )


@alerts_router.get("/stats")
@limiter.limit("50/10minutes")
async def get_statistics(request: Request) -> Dict:
    """Получить статистику по тревогам.

    Возвращает агрегированную статистику о количестве
    регионов с тревогами и без них.

    Args:
        request: FastAPI Request объект

    Returns:
        Dict: Статистика по тревогам
    """
    start_time = time.time()

    try:
        current_status = get_current_status()

        if current_status is None:
            raise HTTPException(status_code=503, detail="Данные еще не загружены")

        # Считаем статистику
        active_count = current_status.active_alerts
        total_count = current_status.total_regions
        inactive_count = total_count - active_count

        stats = {
            "total_regions": total_count,
            "active_alerts": active_count,
            "inactive_regions": inactive_count,
            "alert_percentage": round((active_count / total_count) * 100, 2) if total_count > 0 else 0,
            "last_update": current_status.last_update.isoformat(),
            "api_status": current_status.api_status
        }

        # Записываем метрики
        duration = time.time() - start_time
        metrics_collector.record_http_request(
            method="GET",
            endpoint="/stats",
            status_code=200,
            duration=duration
        )

        logger.info(f"Запрос статистики: {active_count}/{total_count} активных тревог")

        return stats

    except HTTPException:
        raise

    except Exception as e:
        duration = time.time() - start_time
        metrics_collector.record_http_request(
            method="GET",
            endpoint="/stats",
            status_code=500,
            duration=duration
        )

        logger.error(f"Ошибка при получении статистики: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики")


# Функция обработчик для передачи в main.py
def get_rate_limit_handler():
    """Получить обработчик превышения лимита запросов."""
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        """Обработчик превышения лимита запросов."""
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Слишком много запросов",
                "error": "rate_limit_exceeded"
            }
        )
    return rate_limit_handler