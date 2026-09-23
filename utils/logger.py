"""Конфигурация логирования для AirAlarmUA.

Предоставляет централизованную настройку логирования
с использованием loguru и различных output handlers.
"""

import sys
import os
from pathlib import Path
from typing import Optional
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


# Инициализация логирования по умолчанию
# Файловый вывод включается только через LOG_FILE, чтобы импорт модуля
# не создавал файлы и директории как побочный эффект.
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.getenv("LOG_FILE"),
    enable_console=True
)