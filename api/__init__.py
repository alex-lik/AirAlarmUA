"""API роутеры AirAlarmUA.

Содержит FastAPI роутеры для различных эндпоинтов
приложения с разделением ответственности.
"""

from .alerts import alerts_router
from .monitoring import monitoring_router
from .simple import simple_router

__all__ = ["alerts_router", "monitoring_router", "simple_router"]