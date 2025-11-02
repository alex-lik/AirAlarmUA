"""Сервис для работы с API alerts.in.ua.

Обеспечивает получение данных о воздушных тревогах,
обработку ошибок и retry логику.
"""

import time
import asyncio
from typing import Dict, Optional, List
from datetime import datetime

import requests
import sentry_sdk
from loguru import logger

from config import settings, REGIONS_UID_MAP, SORTED_UID_LIST
from models import AlertSystemStatus, ApiError


class AlertsApiService:
    """Сервис для взаимодействия с API alerts.in.ua.

    Предоставляет методы для получения данных о статусах
    воздушных тревог с обработкой ошибок и retry логикой.
    """

    def __init__(self):
        """Инициализация сервиса."""
        self.settings = settings
        self.session = requests.Session()
        self._setup_session()

    def _setup_session(self) -> None:
        """Настройка HTTP сессии."""
        self.session.headers.update({
            "Authorization": f"Bearer {self.settings.alerts_api_token}",
            "Content-Type": "application/json",
            "User-Agent": "AirAlarmUA/1.0.0"
        })

    def _create_error_log(self, error: Exception, retry_count: int = 0) -> ApiError:
        """Создание объекта ошибки для логирования.

        Args:
            error: Исключение
            retry_count: Количество попыток повтора

        Returns:
            ApiError: Объект ошибки для логирования
        """
        return ApiError(
            error_type=type(error).__name__,
            message=str(error),
            retry_count=retry_count
        )

    async def _make_request(self, url: str, retry_count: int = 0) -> requests.Response:
        """Выполнение HTTP запроса с retry логикой.

        Args:
            url: URL запроса
            retry_count: Текущая попытка

        Returns:
            requests.Response: Ответ от API

        Raises:
            requests.RequestException: При ошибке запроса
        """
        try:
            response = self.session.get(
                url,
                timeout=self.settings.request_timeout
            )
            response.raise_for_status()
            return response

        except requests.exceptions.Timeout as e:
            error_log = self._create_error_log(e, retry_count)
            logger.warning(f"Таймаут запроса к API (попытка {retry_count + 1}): {error_log.message}")
            raise

        except requests.exceptions.HTTPError as e:
            error_log = self._create_error_log(e, retry_count)
            logger.warning(f"HTTP ошибка API (попытка {retry_count + 1}): {error_log.message}")
            raise

        except requests.exceptions.RequestException as e:
            error_log = self._create_error_log(e, retry_count)
            logger.error(f"Ошибка запроса к API (попытка {retry_count + 1}): {error_log.message}")
            if self.settings.is_sentry_enabled:
                sentry_sdk.capture_exception(e)
            raise

    def _parse_statuses_string(self, statuses_string: str) -> Dict[str, bool]:
        """Парсинг строки со статусами регионов.

        API возвращает строку, где каждый символ соответствует
        статусу региона в порядке SORTED_UID_LIST.

        Args:
            statuses_string: Строка со статусами

        Returns:
            Dict[str, bool]: Словарь {регион: есть_тревога}
        """
        regions_status = {}

        # API возвращает строку, где:
        # "A" - активная тревога (True)
        # "P" - частичная тревога (True)
        # "N" - нет тревоги (False)

        for i, uid in enumerate(SORTED_UID_LIST):
            if i >= len(statuses_string):
                # Если строка короче, чем регионов, считаем статус "нет тревоги"
                regions_status[REGIONS_UID_MAP[uid]] = False
                continue

            status_char = statuses_string[i].upper()
            region_name = REGIONS_UID_MAP[uid]

            # Преобразуем символ в булево значение
            is_alert = status_char in ['A', 'P']
            regions_status[region_name] = is_alert

        return regions_status

    async def _fetch_data_with_retry(self) -> Optional[Dict[str, bool]]:
        """Получение данных с retry логикой.

        Returns:
            Optional[Dict[str, bool]]: Данные о регионах или None при ошибке
        """
        last_error = None

        for attempt in range(self.settings.max_retries):
            try:
                logger.debug(f"Запрос к API (попытка {attempt + 1})")

                response = await self._make_request(self.settings.alerts_api_url, attempt)

                # API возвращает строку со статусами, а не JSON
                statuses_string = response.text.strip()

                if not statuses_string:
                    raise ValueError("Пустой ответ от API")

                regions_data = self._parse_statuses_string(statuses_string)

                if not regions_data:
                    raise ValueError("Не удалось распарсить статусы регионов")

                logger.info(f"Успешно получены данные для {len(regions_data)} регионов")
                return regions_data

            except Exception as e:
                last_error = e
                error_log = self._create_error_log(e, attempt)

                logger.warning(f"Попытка {attempt + 1} неудачна: {error_log.message}")

                # Ждем перед следующей попыткой (exponential backoff)
                if attempt < self.settings.max_retries - 1:
                    wait_time = min(2 ** attempt, 30)  # Максимум 30 секунд
                    logger.debug(f"Ожидание {wait_time} секунд перед следующей попыткой")
                    await asyncio.sleep(wait_time)

        # Все попытки неудачны
        error_log = self._create_error_log(last_error, self.settings.max_retries)
        logger.error(f"Не удалось получить данные после {self.settings.max_retries} попыток: {error_log.message}")

        if self.settings.is_sentry_enabled:
            sentry_sdk.capture_exception(last_error)

        return None

    async def get_alerts_status(self) -> AlertSystemStatus:
        """Получить текущий статус воздушных тревог.

        Returns:
            AlertSystemStatus: Статус системы оповещения

        Raises:
            ValueError: Если не удалось получить данные
        """
        try:
            regions_data = await self._fetch_data_with_retry()

            if regions_data is None:
                raise ValueError("Не удалось получить данные от API")

            return AlertSystemStatus.create_from_api_response(regions_data)

        except Exception as e:
            logger.error(f"Критическая ошибка при получении статусов: {e}")

            # Возвращаем статус с ошибкой
            return AlertSystemStatus(
                regions={},
                total_regions=0,
                active_alerts=0,
                last_update=datetime.utcnow(),
                update_source="alerts.in.ua API",
                api_status="error"
            )

    async def get_region_status(self, region_name: str) -> Dict[str, bool]:
        """Получить статус для конкретного региона.

        Args:
            region_name: Название региона для поиска

        Returns:
            Dict[str, bool]: Найденные регионы и их статусы
        """
        full_status = await self.get_alerts_status()

        # Ищем регионы, содержащие искомую подстроку
        found_regions = {}
        search_term = region_name.lower()

        for region, status_obj in full_status.regions.items():
            if search_term in region.lower():
                found_regions[region] = status_obj.is_alert

        return found_regions

    def close(self) -> None:
        """Закрыть HTTP сессию."""
        if self.session:
            self.session.close()
            logger.debug("HTTP сессия закрыта")