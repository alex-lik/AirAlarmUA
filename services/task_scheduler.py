"""Сервис планирования задач для обновления данных.

Обеспечивает периодическое обновление статусов тревог
и отправку уведомлений об изменениях.
"""

import asyncio
import time
from typing import Optional
from datetime import datetime

from loguru import logger

from config import settings, PRIORITY_CITIES
from models import AlertSystemStatus
from utils import metrics_collector, get_logger
from services.alerts_api import AlertsApiService
from services.telegram_service import TelegramService

# Инициализация логгера
logger = get_logger(__name__)


class TaskScheduler:
    """Планировщик задач для периодического обновления данных.

    Отвечает за:
    - Периодическое получение данных от API
    - Отправку уведомлений об изменениях
    - Обработку ошибок и retry логику
    - Сбор метрик
    """

    def __init__(
        self,
        alerts_service: AlertsApiService,
        telegram_service: TelegramService
    ):
        """Инициализация планировщика.

        Args:
            alerts_service: Сервис API тревог
            telegram_service: Сервис Telegram уведомлений
        """
        self.alerts_service = alerts_service
        self.telegram_service = telegram_service
        self.settings = settings

        # Состояние планировщика
        self._running = False
        self._last_status: Optional[AlertSystemStatus] = None
        self._failure_count = 0
        self._last_update_time: Optional[datetime] = None

        # Состояние Киева для приоритетных уведомлений
        self._last_kyiv_status: Optional[bool] = None

        logger.info("Планировщик задач инициализирован")

    async def start(self) -> None:
        """Запустить планировщик в фоновом режиме."""
        if self._running:
            logger.warning("Планировщик уже запущен")
            return

        self._running = True
        logger.info("Планировщик задач запущен")

        # Первое обновление данных
        await self.update_alerts_status()

        # Запуск основного цикла
        asyncio.create_task(self._main_loop())

    async def stop(self) -> None:
        """Остановить планировщик."""
        if not self._running:
            return

        self._running = False
        logger.info("Планировщик задач остановлен")

    async def _main_loop(self) -> None:
        """Основной цикл планировщика."""
        while self._running:
            try:
                # Ожидаем до следующего обновления
                await asyncio.sleep(self.settings.update_interval)

                # Обновляем статусы
                await self.update_alerts_status()

            except asyncio.CancelledError:
                logger.info("Планировщик отменен")
                break

            except Exception as e:
                logger.error(f"Ошибка в основном цикле планировщика: {e}")
                # Продолжаем работу несмотря на ошибки

    async def update_alerts_status(self) -> Optional[AlertSystemStatus]:
        """Обновить статусы воздушных тревог.

        Returns:
            Optional[AlertSystemStatus]: Новый статус системы или None при ошибке
        """
        start_time = time.time()

        try:
            logger.debug("Начало обновления статусов тревог")

            # Получаем новые данные
            new_status = await self.alerts_service.get_alerts_status()

            # Проверяем успешность получения данных
            if new_status.api_status != "ok":
                await self._handle_api_failure("API returned error status")
                return None

            # Обрабатываем изменения
            await self._process_status_changes(new_status)

            # Обновляем состояние
            self._last_status = new_status
            self._last_update_time = datetime.utcnow()
            self._failure_count = 0  # Сбрасываем счетчик ошибок

            # Обновляем статус в API модуле
            try:
                from main import update_api_status
                update_api_status(new_status)
            except ImportError:
                logger.warning("Не удалось обновить статус в API модуле")

            # Обновляем метрики
            duration = time.time() - start_time
            metrics_collector.update_alert_metrics(
                active_count=new_status.active_alerts,
                inactive_count=new_status.total_regions - new_status.active_alerts,
                total_regions=new_status.total_regions,
                update_time=new_status.last_update
            )
            metrics_collector.record_api_request("success", duration)

            logger.info(
                f"Статусы успешно обновлены: {new_status.active_alerts}/{new_status.total_regions} активных "
                f"за {duration:.3f}s"
            )

            return new_status

        except Exception as e:
            duration = time.time() - start_time
            await self._handle_api_failure(e, duration)
            return None

    async def _process_status_changes(self, new_status: AlertSystemStatus) -> None:
        """Обработать изменения в статусах тревог.

        Args:
            new_status: Новый статус системы
        """
        if self._last_status is None:
            logger.info("Первичное получение данных, пропускаем проверку изменений")
            return

        changes = []

        # Проверяем изменения для каждого региона
        for region_name, new_region_status in new_status.regions.items():
            if region_name in self._last_status.regions:
                old_region_status = self._last_status.regions[region_name]

                # Проверяем изменение статуса
                if old_region_status.is_alert != new_region_status.is_alert:
                    changes.append({
                        "region": region_name,
                        "old_status": old_region_status.is_alert,
                        "new_status": new_region_status.is_alert,
                        "is_priority": region_name in PRIORITY_CITIES
                    })

        # Отправляем уведомления об изменениях
        if changes:
            logger.info(f"Обнаружено {len(changes)} изменений в статусах")
            await self._send_change_notifications(changes)

            # Проверяем изменения для Киева (особо важные)
            await self._check_kyiv_status_change(new_status)

    async def _send_change_notifications(self, changes: list) -> None:
        """Отправить уведомления об изменениях статусов.

        Args:
            changes: Список изменений в статусах
        """
        if not self.telegram_service.is_enabled:
            return

        try:
            # Группируем изменения по типу
            started_alerts = [c for c in changes if c["new_status"]]
            stopped_alerts = [c for c in changes if not c["new_status"]]

            # Отправляем уведомления о начавшихся тревогах
            for change in started_alerts:
                success = await self.telegram_service.send_alert_notification(
                    region_name=change["region"],
                    is_alert=True,
                    previous_status=change["old_status"]
                )

                metrics_collector.record_telegram_notification(
                    "success" if success else "error"
                )

            # Отправляем уведомления об отбоях
            for change in stopped_alerts:
                success = await self.telegram_service.send_alert_notification(
                    region_name=change["region"],
                    is_alert=False,
                    previous_status=change["old_status"]
                )

                metrics_collector.record_telegram_notification(
                    "success" if success else "error"
                )

        except Exception as e:
            logger.error(f"Ошибка при отправке уведомлений об изменениях: {e}")

    async def _check_kyiv_status_change(self, new_status: AlertSystemStatus) -> None:
        """Проверить изменение статуса для Киева.

        Args:
            new_status: Новый статус системы
        """
        kyiv_region = "м. Київ"

        if kyiv_region not in new_status.regions:
            return

        current_kyiv_status = new_status.regions[kyiv_region].is_alert

        if self._last_kyiv_status != current_kyiv_status:
            self._last_kyiv_status = current_kyiv_status

            # Отправляем приоритетное уведомление для Киева
            if self.telegram_service.is_enabled:
                if current_kyiv_status:
                    message = "🚨 В Киеве воздушная тревога!"
                else:
                    message = "✅ В Киеве отбой воздушной тревоги."

                success = await self.telegram_service.send_message(message)
                metrics_collector.record_telegram_notification(
                    "success" if success else "error"
                )

                logger.info(f"Отправлено уведомление об изменении статуса Киева: {message}")

    async def _handle_api_failure(self, error: Exception, duration: float = 0) -> None:
        """Обработать ошибку API.

        Args:
            error: Ошибка
            duration: Длительность запроса
        """
        self._failure_count += 1

        metrics_collector.record_api_request("error", duration)
        metrics_collector.update_system_status(False)

        logger.error(f"Ошибка API (счетчик: {self._failure_count}): {error}")

        # Проверяем достижение максимального количества ошибок
        if self._failure_count >= self.settings.max_failures:
            logger.critical(f"Достигнуто максимальное количество ошибок: {self._failure_count}")

            # Отправляем системное уведомление
            if self.telegram_service.is_enabled:
                await self.telegram_service.send_system_alert(
                    f"Проблемы с API alerts.in.ua - {self._failure_count} последовательных ошибок",
                    priority="high"
                )

            # Сбрасываем счетчик после отправки уведомления
            self._failure_count = 0

    @property
    def is_running(self) -> bool:
        """Проверить, запущен ли планировщик.

        Returns:
            bool: True если планировщик запущен
        """
        return self._running

    @property
    def last_status(self) -> Optional[AlertSystemStatus]:
        """Получить последний статус системы.

        Returns:
            Optional[AlertSystemStatus]: Последний полученный статус
        """
        return self._last_status

    @property
    def failure_count(self) -> int:
        """Получить количество последовательных ошибок.

        Returns:
            int: Количество ошибок
        """
        return self._failure_count

    @property
    def last_update_time(self) -> Optional[datetime]:
        """Получить время последнего обновления.

        Returns:
            Optional[datetime]: Время последнего успешного обновления
        """
        return self._last_update_time