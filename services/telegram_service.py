"""Сервис для отправки уведомлений в Telegram.

Обеспечивает интеграцию с Telegram Bot API для отправки
уведомлений о воздушных тревогах.
"""

from typing import Optional, List
from datetime import datetime

import requests
from loguru import logger

from config import settings, PRIORITY_CITIES


class TelegramService:
    """Сервис для отправки уведомлений в Telegram.

    Предоставляет методы для отправки сообщений через Telegram Bot API
    с обработкой ошибок и форматированием.
    """

    def __init__(self):
        """Инициализация сервиса."""
        self.settings = settings
        self.base_url = f"https://api.telegram.org/bot{self.settings.telegram_token}"
        self.last_kyiv_status: Optional[bool] = None

    @property
    def is_enabled(self) -> bool:
        """Проверяет, включен ли Telegram сервис.

        Returns:
            bool: True если токен и chat_id настроены
        """
        return self.settings.is_telegram_enabled

    async def send_message(
        self,
        message: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML"
    ) -> bool:
        """Отправить сообщение в Telegram.

        Args:
            message: Текст сообщения
            chat_id: ID чата (если None, используется из настроек)
            parse_mode: Режим парсинга (HTML, Markdown)

        Returns:
            bool: True если сообщение отправлено успешно
        """
        if not self.is_enabled:
            logger.warning("Telegram не настроен, сообщение не отправлено")
            return False

        try:
            target_chat_id = chat_id or self.settings.telegram_chat_id

            payload = {
                "chat_id": target_chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }

            # Добавляем время отправки
            timestamp = datetime.now().strftime("%H:%M:%S")
            logger.debug(f"Отправка сообщения в Telegram (время: {timestamp})")

            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=10
            )

            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                logger.info("Сообщение успешно отправлено в Telegram")
                return True
            else:
                error_desc = result.get("description", "Unknown error")
                logger.error(f"Ошибка Telegram API: {error_desc}")
                return False

        except requests.exceptions.Timeout:
            logger.error("Таймаут при отправке сообщения в Telegram")
            return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при отправке в Telegram: {e}")
            return False

        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке в Telegram: {e}")
            return False

    async def send_alert_notification(
        self,
        region_name: str,
        is_alert: bool,
        previous_status: Optional[bool] = None
    ) -> bool:
        """Отправить уведомление об изменении статуса тревоги.

        Args:
            region_name: Название региона
            is_alert: Текущий статус тревоги
            previous_status: Предыдущий статус

        Returns:
            bool: True если уведомление отправлено успешно
        """
        if not self.is_enabled:
            return False

        # Не отправляем уведомление если статус не изменился
        if previous_status is not None and is_alert == previous_status:
            return False

        # Формируем сообщение в зависимости от типа уведомления
        if region_name in PRIORITY_CITIES:
            message = self._format_priority_city_alert(region_name, is_alert)
        else:
            message = self._format_region_alert(region_name, is_alert)

        return await self.send_message(message)

    async def send_system_alert(self, message: str, priority: str = "high") -> bool:
        """Отправить системное уведомление.

        Args:
            message: Текст сообщения
            priority: Приоритет уведомления

        Returns:
            bool: True если сообщение отправлено успешно
        """
        if not self.is_enabled:
            return False

        formatted_message = f"🔧 <b>Системное уведомление</b>\n\n{message}"

        if priority == "high":
            formatted_message = "‼️ " + formatted_message

        return await self.send_message(formatted_message)

    async def send_daily_summary(
        self,
        active_regions: List[str],
        total_regions: int,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """Отправить суточную сводку.

        Args:
            active_regions: Список регионов с тревогой
            total_regions: Общее количество регионов
            timestamp: Время формирования сводки

        Returns:
            bool: True если сообщение отправлено успешно
        """
        if not self.is_enabled:
            return False

        time_str = timestamp.strftime("%d.%m.%Y %H:%M") if timestamp else datetime.now().strftime("%d.%m.%Y %H:%M")
        active_count = len(active_regions)
        inactive_count = total_regions - active_count

        message = f"""📊 <b>Сводка по воздушным тревогам</b>
🕐 <i>{time_str}</i>

🚨 <b>Активные тревоги:</b> {active_count}
✅ <b>Спокойно:</b> {inactive_count}
📊 <b>Всего регионов:</b> {total_regions}"""

        if active_regions:
            message += "\n\n<b>Регионы с тревогой:</b>\n"
            for region in sorted(active_regions):
                message += f"• {region}\n"

        return await self.send_message(message)

    def _format_priority_city_alert(self, city_name: str, is_alert: bool) -> str:
        """Сформатировать уведомление для приоритетного города.

        Args:
            city_name: Название города
            is_alert: Статус тревоги

        Returns:
            str: Отформатированное сообщение
        """
        if is_alert:
            return f"""🚨🚨 <b>ВНИМАНИЕ! ВОЗДУШНАЯ ТРЕВОГА</b> 🚨🚨

📍 <b>{city_name}</b>

⚠️ Немедленно уйдите в укрытие!
⚠️ Следуйте инструкциям гражданской обороны!

<i>Время: {datetime.now().strftime("%H:%M:%S")}</i>"""
        else:
            return f"""✅ <b>ОТБОЙ ВОЗДУШНОЙ ТРЕВОГИ</b>

📍 <b>{city_name}</b>

ℹ️ Можно покинуть укрытие
ℹ️ Следите за дальнейшими сообщениями

<i>Время: {datetime.now().strftime("%H:%M:%S")}</i>"""

    def _format_region_alert(self, region_name: str, is_alert: bool) -> str:
        """Сформатировать уведомление для региона.

        Args:
            region_name: Название региона
            is_alert: Статус тревоги

        Returns:
            str: Отформатированное сообщение
        """
        if is_alert:
            return f"⚠️ <b>Воздушная тревога</b>\n\n📍 {region_name}\n<i>{datetime.now().strftime('%H:%M:%S')}</i>"
        else:
            return f"✅ <b>Отбой тревоги</b>\n\n📍 {region_name}\n<i>{datetime.now().strftime('%H:%M:%S')}</i>"

    async def check_connection(self) -> bool:
        """Проверить соединение с Telegram API.

        Returns:
            bool: True если соединение работает
        """
        if not self.is_enabled:
            return False

        try:
            response = requests.get(
                f"{self.base_url}/getMe",
                timeout=5
            )
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                bot_info = result.get("result", {})
                logger.info(f"Telegram бот {bot_info.get('username')} доступен")
                return True
            else:
                logger.error("Telegram API вернул ошибку")
                return False

        except Exception as e:
            logger.error(f"Ошибка проверки соединения с Telegram: {e}")
            return False