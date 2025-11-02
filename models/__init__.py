"""Модели данных AirAlarmUA.

Содержит Pydantic модели для валидации данных
о статусах тревог и других сущностей системы.
"""

from .alert import (
    AlertStatus,
    RegionStatus,
    AlertSystemStatus,
    ApiError,
    NotificationMessage,
    HealthCheckResponse
)

__all__ = [
    "AlertStatus",
    "RegionStatus",
    "AlertSystemStatus",
    "ApiError",
    "NotificationMessage",
    "HealthCheckResponse"
]