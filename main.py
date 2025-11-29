"""Основной файл приложения AirAlarmUA.

FastAPI приложение для мониторинга воздушных тревог в Украине
с интеграцией Telegram уведомлений и Prometheus метрик.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from loguru import logger

from config import settings
from services import AlertsApiService, TelegramService, TaskScheduler
from api import alerts_router, monitoring_router
from utils import metrics_collector, get_logger

# Инициализация логгера
logger = get_logger(__name__)

# Глобальные переменные для сервисов
_alerts_service: Optional[AlertsApiService] = None
_telegram_service: Optional[TelegramService] = None
_scheduler: Optional[TaskScheduler] = None


def create_application() -> FastAPI:
    """Создать и настроить FastAPI приложение.

    Returns:
        FastAPI: Настроенное приложение
    """
    # Инициализация Sentry
    _setup_sentry()

    # Создание приложения
    app = FastAPI(
        title="AirAlarmUA API",
        description="API для мониторинга воздушных тревог в Украине",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Настройка middleware
    _setup_middleware(app)

    # Настройка роутеров
    _setup_routers(app)

    # Настройка обработчиков ошибок
    _setup_exception_handlers(app)

    # Настройка Prometheus инструментации
    _setup_prometheus(app)

    return app


def _setup_sentry() -> None:
    """Настроить Sentry для мониторинга ошибок."""
    if settings.is_sentry_enabled:
        try:
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                send_default_pii=True,
                traces_sample_rate=0.1,
                environment="production" if settings.cors_origins != ["*"] else "development"
            )
            logger.info("Sentry инициализирован для мониторинга ошибок")
        except Exception as e:
            logger.error(f"Ошибка инициализации Sentry: {e}")
    else:
        logger.info("Sentry отключен")


def _setup_middleware(app: FastAPI) -> None:
    """Настроить middleware приложения.

    Args:
        app: FastAPI приложение
    """
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"]
    )

    # Rate limiting
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter

    logger.info("Middleware настроены")


def _setup_routers(app: FastAPI) -> None:
    """Настроить роутеры приложения.

    Args:
        app: FastAPI приложение
    """
    # API роутеры
    app.include_router(alerts_router)
    app.include_router(monitoring_router)

    logger.info("Роутеры настроены")


def _setup_exception_handlers(app: FastAPI) -> None:
    """Настроить обработчики исключений.

    Args:
        app: FastAPI приложение
    """
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        """Обработчик превышения лимита запросов."""
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Слишком много запросов",
                "error": "rate_limit_exceeded",
                "retry_after": "60"
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Общий обработчик исключений."""
        logger.error(f"Необработанная ошибка: {exc}", exc_info=True)

        if settings.is_sentry_enabled:
            sentry_sdk.capture_exception(exc)

        metrics_collector.record_http_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=500,
            duration=0
        )

        return JSONResponse(
            status_code=500,
            content={
                "detail": "Внутренняя ошибка сервера",
                "error": "internal_server_error"
            }
        )

    logger.info("Обработчики исключений настроены")


def _setup_prometheus(app: FastAPI) -> None:
    """Настроить Prometheus метрики.

    Args:
        app: FastAPI приложение
    """
    try:
        Instrumentator(
            should_group_status_codes=False,
            should_ignore_untemplated=True,
            should_group_untemplated=True,
            should_instrument_requests_inprogress=False,
            excluded_handlers=["/metrics"],
            env_var_name="ENABLE_METRICS",
            inprogress_name="fastapi_inprogress",
            inprogress_labels=True,
        ).instrument(app).expose(app)

        logger.info("Prometheus метрики настроены")
    except Exception as e:
        logger.error(f"Ошибка настройки Prometheus: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Контекстный менеджер жизненного цикла приложения.

    Args:
        app: FastAPI приложение
    """
    logger.info("Запуск приложения AirAlarmUA")

    # Инициализация сервисов
    await initialize_services()

    # Запуск планировщика задач
    await start_scheduler()

    logger.info("Приложение успешно запущено")

    try:
        yield
    finally:
        logger.info("Остановка приложения")
        await cleanup_services()
        logger.info("Приложение остановлено")


async def initialize_services() -> None:
    """Инициализировать сервисы приложения."""
    global _alerts_service, _telegram_service, _scheduler

    try:
        # Инициализация API сервиса
        _alerts_service = AlertsApiService()
        logger.info("Сервис API тревог инициализирован")

        # Инициализация Telegram сервиса
        _telegram_service = TelegramService()
        if _telegram_service.is_enabled:
            # Проверяем соединение с Telegram
            if await _telegram_service.check_connection():
                logger.info("Telegram сервис инициализирован и подключен")
            else:
                logger.warning("Telegram сервис инициализирован, но соединение не установлено")
        else:
            logger.info("Telegram сервис отключен (не настроен)")

    except Exception as e:
        logger.error(f"Ошибка инициализации сервисов: {e}")
        raise


async def start_scheduler() -> None:
    """Запустить планировщик задач."""
    global _scheduler, _alerts_service, _telegram_service

    if _alerts_service is None or _telegram_service is None:
        raise RuntimeError("Сервисы не инициализированы")

    try:
        _scheduler = TaskScheduler(
            alerts_service=_alerts_service,
            telegram_service=_telegram_service
        )

        await _scheduler.start()
        logger.info("Планировщик задач запущен")

    except Exception as e:
        logger.error(f"Ошибка запуска планировщика: {e}")
        raise


async def cleanup_services() -> None:
    """Очистить ресурсы сервисов."""
    global _scheduler, _alerts_service, _telegram_service

    try:
        # Остановка планировщика
        if _scheduler:
            await _scheduler.stop()
            _scheduler = None
            logger.info("Планировщик задач остановлен")

        # Закрытие API сервиса
        if _alerts_service:
            _alerts_service.close()
            _alerts_service = None
            logger.info("Сервис API тревог закрыт")

        # Telegram сервис не требует специальной очистки
        _telegram_service = None

    except Exception as e:
        logger.error(f"Ошибка очистки сервисов: {e}")


def get_alerts_service() -> Optional[AlertsApiService]:
    """Получить экземпляр сервиса API тревог.

    Returns:
        Optional[AlertsApiService]: Сервис или None если не инициализирован
    """
    return _alerts_service


def get_telegram_service() -> Optional[TelegramService]:
    """Получить экземпляр Telegram сервиса.

    Returns:
        Optional[TelegramService]: Сервис или None если не инициализирован
    """
    return _telegram_service


def get_scheduler() -> Optional[TaskScheduler]:
    """Получить экземпляр планировщика задач.

    Returns:
        Optional[TaskScheduler]: Планировщик или None если не инициализирован
    """
    return _scheduler


def update_api_status(status) -> None:
    """Обновить статус в API модуле.

    Args:
        status: Новый статус системы
    """
    try:
        from api.alerts import set_current_status
        set_current_status(status)
    except ImportError:
        logger.warning("Не удалось импортировать set_current_status из api.alerts")


# Создание приложения
app = create_application()


# Эндпоинт для тестирования (только в development)
@app.get("/debug/services")
async def debug_services():
    """Отладочный эндпоинт для проверки состояния сервисов."""
    if settings.cors_origins != ["*"]:
        return {"error": "Debug endpoint disabled in production"}

    return {
        "alerts_service": _alerts_service is not None,
        "telegram_service": {
            "initialized": _telegram_service is not None,
            "enabled": _telegram_service.is_enabled if _telegram_service else False
        },
        "scheduler": {
            "initialized": _scheduler is not None,
            "running": _scheduler.is_running if _scheduler else False,
            "failure_count": _scheduler.failure_count if _scheduler else 0,
            "last_update": _scheduler.last_update_time.isoformat() if _scheduler and _scheduler.last_update_time else None
        }
    }


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Запуск сервера на порту {settings.port}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
        log_level="info"
    )