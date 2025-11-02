"""Модуль конфигурации AirAlarmUA.

Содержит настройки приложения и константы.
"""

from .settings import settings
from .regions import REGIONS_UID_MAP, REGIONS_LIST, SORTED_UID_LIST, PRIORITY_CITIES

__all__ = ["settings", "REGIONS_UID_MAP", "REGIONS_LIST", "SORTED_UID_LIST", "PRIORITY_CITIES"]