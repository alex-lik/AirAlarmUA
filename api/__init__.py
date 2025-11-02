"""API роутеры AirAlarmUA.

Содержит FastAPI роутеры для различных эндпоинтов
приложения с разделением ответственности.
"""

from .alerts import alerts_router
from .monitoring import monitoring_router

__all__ = ["alerts_router", "monitoring_router"]