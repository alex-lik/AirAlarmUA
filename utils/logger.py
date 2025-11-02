"""Конфигурация логирования для AirAlarmUA.

Предоставляет централизованную настройку логирования
с использованием loguru и различных output handlers.
"""

import sys
import os
from pathlib import Path
from typing import Optional, List
from loguru import logger


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    rotation: str = "1 day",
    retention: str = "10 days",
    enable_console: bool = True
) -> None:
    """Настроить логирование для приложения.

    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Путь к файлу логов
        rotation: Период ротации логов
        retention: Период хранения логов
        enable_console: Включить вывод в консоль
    """
    # Удаляем стандартный handler
    logger.remove()

    # Формат логов
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Консольный вывод
    if enable_console:
        logger.add(
            sys.stdout,
            format=log_format,
            level=log_level,
            colorize=True,
            backtrace=True,
            diagnose=True
        )

    # Файловый вывод
    if log_file:
        # Создаем директорию для логов если не существует
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            format=log_format,
            level=log_level,
            rotation=rotation,
            retention=retention,
            compression="zip",
            backtrace=True,
            diagnose=True
        )

        # Отдельный файл для ошибок
        error_log_file = log_path.parent / f"{log_path.stem}_errors{log_path.suffix}"
        logger.add(
            error_log_file,
            format=log_format,
            level="ERROR",
            rotation=rotation,
            retention=retention,
            compression="zip",
            backtrace=True,
            diagnose=True
        )

    logger.info(f"Логирование настроено с уровнем: {log_level}")


def get_logger(name: str = None):
    """Получить логгер для конкретного модуля.

    Args:
        name: Имя модуля

    Returns:
        Logger: Экземпляр логгера
    """
    if name:
        return logger.bind(name=name)
    return logger


class ContextLogger:
    """Контекстный логгер для добавления контекста к сообщениям.

    Позволяет добавлять контекстную информацию (request_id, user_id и т.д.)
    ко всем сообщениям в рамках одного контекста.
    """

    def __init__(self, **context):
        """Инициализация контекстного логгера.

        Args:
            **context: Контекстные параметры
        """
        self.context = context
        self.logger = logger.bind(**context)

    def info(self, message: str, **kwargs):
        """Логировать INFO сообщение."""
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Логировать WARNING сообщение."""
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        """Логировать ERROR сообщение."""
        self.logger.error(message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Логировать DEBUG сообщение."""
        self.logger.debug(message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Логировать CRITICAL сообщение."""
        self.logger.critical(message, **kwargs)

    def bind(self, **kwargs):
        """Добавить новый контекст.

        Args:
            **kwargs: Новые контекстные параметры

        Returns:
            ContextLogger: Новый экземпляр с расширенным контекстом
        """
        new_context = {**self.context, **kwargs}
        return ContextLogger(**new_context)


def log_function_call(func_name: str, args: tuple = None, kwargs: dict = None):
    """Логировать вызов функции.

    Args:
        func_name: Имя функции
        args: Позиционные аргументы
        kwargs: Именованные аргументы
    """
    args_str = str(args) if args else "()"
    kwargs_str = str(kwargs) if kwargs else ""

    if kwargs_str:
        full_args = f"{args_str}, {kwargs_str}"
    else:
        full_args = args_str

    logger.debug(f"Вызов функции {func_name}{full_args}")


def log_api_request(method: str, url: str, status_code: int, duration: float):
    """Логировать API запрос.

    Args:
        method: HTTP метод
        url: URL запроса
        status_code: Код ответа
        duration: Длительность запроса
    """
    status_emoji = "✅" if 200 <= status_code < 300 else "❌"
    logger.info(
        f"{status_emoji} {method} {url} -> {status_code} ({duration:.3f}s)"
    )


def log_error_with_context(error: Exception, context: dict = None):
    """Логировать ошибку с контекстом.

    Args:
        error: Исключение
        context: Контекстная информация
    """
    context_str = f" | Контекст: {context}" if context else ""
    logger.error(f"Ошибка: {type(error).__name__}: {error}{context_str}")


# Инициализация логирования по умолчанию
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_file="./logs/today.log",
    enable_console=True
)