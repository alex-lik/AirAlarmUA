"""Конфигурация приложения AirAlarmUA.

Модуль содержит настройки приложения, переменные окружения
и конфигурацию различных сервисов.
"""

import os
from typing import Optional
from dotenv import load_dotenv
load_dotenv()


class Settings:
    """Класс настроек приложения с валидацией.

    Загружает переменные окружения и предоставляет
    значения по умолчанию с валидацией.
    """

    def __init__(self):
        """Инициализация настроек из переменных окружения."""
        # Настройки Telegram
        self.telegram_token = os.getenv("TELEGRAM_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        # Настройки API alerts.in.ua
        self.alerts_api_token = os.getenv("ALERTS_API_TOKEN", "development_token")
        self.alerts_api_url = os.getenv(
            "ALERTS_API_URL",
            "https://api.alerts.in.ua/v1/iot/active_air_raid_alerts.json"
        )

        # Настройки мониторинга
        self.sentry_dsn = os.getenv("SENTRY_DSN")

        # Настройки приложения
        self.update_interval = int(os.getenv("UPDATE_INTERVAL", "60"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.max_failures = int(os.getenv("MAX_FAILURES", "5"))
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "15"))

        # Настройки rate limiting
        self.rate_limit = os.getenv("RATE_LIMIT", "100/10minutes")

        # Настройки порта
        self.port = int(os.getenv("PORT", "8500"))

        # CORS настройки
        cors_origins_env = os.getenv("CORS_ORIGINS", "*")
        self.cors_origins = [origin.strip() for origin in cors_origins_env.split(",")]

        # Валидация настроек
        self._validate_settings()

    def _validate_settings(self):
        """Провести валидацию настроек."""
        # Валидация токена Telegram
        if self.telegram_token and not self.telegram_token.find(':'):
            raise ValueError('Некорректный формат токена Telegram')

        # Валидация токена API alerts.in.ua (только если не в development режиме)
        if not self.alerts_api_token or len(self.alerts_api_token) < 10:
            # Пропускаем валидацию в development если токен не задан
            if self.alerts_api_token == "":
                import warnings
                warnings.warn("ALERTS_API_TOKEN не настроен, приложение работает в development режиме")
            else:
                raise ValueError('Токен API alerts.in.ua должен содержать минимум 10 символов')

        # Валидация положительных числовых значений
        if self.update_interval <= 0:
            raise ValueError('UPDATE_INTERVAL должен быть положительным числом')
        if self.max_retries <= 0:
            raise ValueError('MAX_RETRIES должен быть положительным числом')
        if self.max_failures <= 0:
            raise ValueError('MAX_FAILURES должен быть положительным числом')
        if self.request_timeout <= 0:
            raise ValueError('REQUEST_TIMEOUT должен быть положительным числом')

        # Валидация порта
        if not (1 <= self.port <= 65535):
            raise ValueError('PORT должен быть в диапазоне 1-65535')

    @property
    def is_telegram_enabled(self) -> bool:
        """Проверяет, настроены ли уведомления Telegram.

        Returns:
            bool: True если токен и chat_id настроены
        """
        return bool(self.telegram_token and self.telegram_chat_id)

    @property
    def is_sentry_enabled(self) -> bool:
        """Проверяет, настроен ли Sentry.

        Returns:
            bool: True если DSN настроен
        """
        return bool(self.sentry_dsn and self.sentry_dsn.strip())


# Глобальный экземпляр настроек
settings = Settings()