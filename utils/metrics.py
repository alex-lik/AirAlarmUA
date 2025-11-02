"""Модуль для работы с Prometheus метриками.

Предоставляет инструменты для сбора и экспорта метрик
производительности и статуса системы.
"""

import time
from typing import Dict, Optional
from datetime import datetime

from prometheus_client import Gauge, Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import CollectorRegistry
from loguru import logger


class MetricsCollector:
    """Коллектор Prometheus метрик для AirAlarmUA.

    Сбор метрик:
    - Количество активных тревог по регионам
    - Время последнего обновления данных
    - Количество запросов к API
    - Время ответа API
    - Статус работы системы
    """

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """Инициализация коллектора метрик.

        Args:
            registry: Реестр метрик Prometheus
        """
        self.registry = registry or CollectorRegistry()

        # Метрики статуса тревог
        self.active_regions = Gauge(
            'air_alert_regions_total',
            'Количество регионов по статусу тревоги',
            ['status'],
            registry=self.registry
        )

        # Метрики времени обновления
        self.last_update_timestamp = Gauge(
            'air_alert_last_update_timestamp',
            'Последнее обновление данных в формате UNIX времени',
            registry=self.registry
        )

        # Метрики API запросов
        self.api_requests_total = Counter(
            'air_alert_api_requests_total',
            'Общее количество запросов к API',
            ['status'],
            registry=self.registry
        )

        self.api_request_duration = Histogram(
            'air_alert_api_request_duration_seconds',
            'Время выполнения запроса к API',
            registry=self.registry
        )

        # Метрики Telegram уведомлений
        self.telegram_notifications_total = Counter(
            'air_alert_telegram_notifications_total',
            'Общее количество отправленных уведомлений в Telegram',
            ['status'],
            registry=self.registry
        )

        # Метрики HTTP endpoints
        self.http_requests_total = Counter(
            'air_alert_http_requests_total',
            'Общее количество HTTP запросов',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )

        self.http_request_duration = Histogram(
            'air_alert_http_request_duration_seconds',
            'Время выполнения HTTP запроса',
            ['method', 'endpoint'],
            registry=self.registry
        )

        # Метрики работы системы
        self.system_status = Gauge(
            'air_alert_system_status',
            'Статус работы системы (1 - работает, 0 - ошибка)',
            registry=self.registry
        )

        self.start_time = Gauge(
            'air_alert_start_time_timestamp',
            'Время запуска приложения в формате UNIX времени',
            registry=self.registry
        )

        # Устанавливаем время запуска
        self.start_time.set(time.time())

        logger.info("Коллектор Prometheus метрик инициализирован")

    def update_alert_metrics(
        self,
        active_count: int,
        inactive_count: int,
        total_regions: int,
        update_time: Optional[datetime] = None
    ) -> None:
        """Обновить метрики статуса тревог.

        Args:
            active_count: Количество регионов с активной тревогой
            inactive_count: Количество регионов без тревоги
            total_regions: Общее количество регионов
            update_time: Время последнего обновления
        """
        try:
            self.active_regions.labels(status='active').set(active_count)
            self.active_regions.labels(status='inactive').set(inactive_count)

            # Добавляем метрику для общего количества регионов
            self.active_regions.labels(status='total').set(total_regions)

            if update_time:
                self.last_update_timestamp.set(update_time.timestamp())
            else:
                self.last_update_timestamp.set(time.time())

            logger.debug(f"Метрики тревог обновлены: активных={active_count}, неактивных={inactive_count}")

        except Exception as e:
            logger.error(f"Ошибка при обновлении метрик тревог: {e}")

    def record_api_request(self, status: str, duration: float) -> None:
        """Записать метрику запроса к API.

        Args:
            status: Статус запроса (success, error, timeout)
            duration: Длительность запроса в секундах
        """
        try:
            self.api_requests_total.labels(status=status).inc()
            self.api_request_duration.observe(duration)

            logger.debug(f"Записана метрика API: статус={status}, длительность={duration:.3f}s")

        except Exception as e:
            logger.error(f"Ошибка при записи метрики API запроса: {e}")

    def record_telegram_notification(self, status: str) -> None:
        """Записать метрику уведомления Telegram.

        Args:
            status: Статус отправки (success, error, disabled)
        """
        try:
            self.telegram_notifications_total.labels(status=status).inc()
            logger.debug(f"Записана метрика Telegram уведомления: статус={status}")

        except Exception as e:
            logger.error(f"Ошибка при записи метрики Telegram: {e}")

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float
    ) -> None:
        """Записать метрику HTTP запроса.

        Args:
            method: HTTP метод
            endpoint: Эндпоинт
            status_code: Код статуса ответа
            duration: Длительность запроса в секундах
        """
        try:
            status_category = 'success' if 200 <= status_code < 300 else 'error'

            self.http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=status_category
            ).inc()

            self.http_request_duration.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)

            logger.debug(
                f"Записана метрика HTTP: {method} {endpoint} -> {status_code} ({duration:.3f}s)"
            )

        except Exception as e:
            logger.error(f"Ошибка при записи метрики HTTP запроса: {e}")

    def update_system_status(self, is_healthy: bool) -> None:
        """Обновить метрику статуса системы.

        Args:
            is_healthy: True если система работает корректно
        """
        try:
            status_value = 1 if is_healthy else 0
            self.system_status.set(status_value)

            status_str = "здоров" if is_healthy else "ошибка"
            logger.debug(f"Статус системы обновлен: {status_str}")

        except Exception as e:
            logger.error(f"Ошибка при обновлении метрики статуса системы: {e}")

    def get_metrics(self) -> str:
        """Получить все метрики в формате Prometheus.

        Returns:
            str: Метрики в формате Prometheus
        """
        try:
            metrics_data = generate_latest(self.registry)
            return metrics_data.decode('utf-8')

        except Exception as e:
            logger.error(f"Ошибка при генерации метрик: {e}")
            return ""

    def get_metrics_summary(self) -> Dict[str, float]:
        """Получить сводную информацию о метриках.

        Returns:
            Dict[str, float]: Словарь с основными метриками
        """
        try:
            # Получаем значения метрик через реестр
            summary = {}

            for metric in self.registry._collector_to_names:
                for name, collector in self.registry._collector_to_names.items():
                    if hasattr(collector, '_value'):
                        summary[name] = collector._value

            return summary

        except Exception as e:
            logger.error(f"Ошибка при получении сводки метрик: {e}")
            return {}


# Глобальный экземпляр коллектора метрик
metrics_collector = MetricsCollector()