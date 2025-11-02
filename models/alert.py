"""Модели данных для системы оповещения о воздушных тревогах.

Содержит Pydantic модели для валидации и сериализации данных
о статусах тревог в различных регионах Украины.
"""

from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class AlertStatus(str, Enum):
    """Статусы воздушной тревоги."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class RegionStatus(BaseModel):
    """Модель статуса тревоги для конкретного региона.

    Attributes:
        region_name: Название региона
        is_alert: Флаг наличия тревоги
        alert_type: Тип тревоги
        last_updated: Время последнего обновления
    """

    region_name: str = Field(..., description="Название региона")
    is_alert: bool = Field(..., description="Флаг наличия тревоги")
    alert_type: AlertStatus = Field(..., description="Тип тревоги")
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="Время последнего обновления статуса"
    )


class AlertSystemStatus(BaseModel):
    """Общий статус системы оповещения.

    Attributes:
        regions: Словарь со статусами всех регионов
        total_regions: Общее количество регионов
        active_alerts: Количество регионов с активной тревогой
        last_update: Время последнего обновления данных
        update_source: Источник данных о статусах
        api_status: Статус работы с внешним API
    """

    regions: Dict[str, RegionStatus] = Field(..., description="Статусы регионов")
    total_regions: int = Field(..., description="Общее количество регионов")
    active_alerts: int = Field(..., description="Количество активных тревог")
    last_update: datetime = Field(..., description="Время последнего обновления")
    update_source: str = Field(default="alerts.in.ua API", description="Источник данных")
    api_status: str = Field(default="ok", description="Статус внешнего API")

    @classmethod
    def create_from_api_response(cls, regions_data: Dict[str, bool]) -> "AlertSystemStatus":
        """Создание статуса системы из ответа API.

        Args:
            regions_data: Словарь с данными о регионах от API

        Returns:
            AlertSystemStatus: Объект статуса системы
        """
        now = datetime.utcnow()
        regions_dict = {}

        for region_name, is_alert in regions_data.items():
            # Определяем тип тревоги на основе статуса
            alert_type = AlertStatus.ACTIVE if is_alert else AlertStatus.INACTIVE

            regions_dict[region_name] = RegionStatus(
                region_name=region_name,
                is_alert=is_alert,
                alert_type=alert_type,
                last_updated=now
            )

        active_count = sum(1 for status in regions_data.values() if status)

        return cls(
            regions=regions_dict,
            total_regions=len(regions_data),
            active_alerts=active_count,
            last_update=now,
            api_status="ok"
        )


class ApiError(BaseModel):
    """Модель ошибки API.

    Attributes:
        error_type: Тип ошибки
        message: Сообщение об ошибке
        retry_count: Количество попыток повтора
        timestamp: Время возникновения ошибки
    """

    error_type: str = Field(..., description="Тип ошибки")
    message: str = Field(..., description="Сообщение об ошибке")
    retry_count: int = Field(default=0, description="Количество попыток повтора")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Время возникновения ошибки"
    )


class NotificationMessage(BaseModel):
    """Модель уведомления.

    Attributes:
        message: Текст сообщения
        priority: Приоритет уведомления
        timestamp: Время создания уведомления
        channels: Каналы отправки
    """

    message: str = Field(..., description="Текст сообщения")
    priority: str = Field(default="normal", description="Приоритет уведомления")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Время создания уведомления"
    )
    channels: List[str] = Field(
        default_factory=lambda: ["telegram"],
        description="Каналы отправки уведомления"
    )


class HealthCheckResponse(BaseModel):
    """Модель ответа health check endpoint.

    Attributes:
        status: Статус сервиса
        timestamp: Время проверки
        version: Версия приложения
        dependencies: Статусы зависимостей
    """

    status: str = Field(..., description="Статус сервиса")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Время проверки"
    )
    version: str = Field(default="1.0.0", description="Версия приложения")
    dependencies: Dict[str, str] = Field(
        default_factory=dict,
        description="Статусы зависимостей"
    )