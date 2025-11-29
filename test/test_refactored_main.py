"""Тесты для рефакторингованного приложения AirAlarmUA.

Проверяют работу новой модульной архитектуры с сервисами,
конфигурацией и разделением ответственности.
"""

import pytest
import asyncio
from unittest.mock import patch, Mock, AsyncMock
from fastapi.testclient import TestClient

# Импортируем основное приложение и сервисы
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, create_application
from config import settings
from services.alerts_api import AlertsApiService
from services.telegram_service import TelegramService
from services.task_scheduler import TaskScheduler

# Создаем тестовый клиент
client = TestClient(app)


class TestApplicationCreation:
    """Тесты создания приложения."""

    def test_create_application_success(self):
        """Т успешного создания FastAPI приложения."""
        app_instance = create_application()
        assert app_instance is not None
        assert hasattr(app_instance, 'router')

    def test_app_creation_with_factory(self):
        """Т создания приложения через фабрику."""
        assert app is not None
        assert app.title == "FastAPI"
        assert hasattr(app, 'middleware')


class TestConfiguration:
    """Тесты конфигурации."""

    def test_settings_creation(self):
        """Т создания настроек."""
        assert settings is not None
        assert hasattr(settings, 'alerts_api_token')
        assert hasattr(settings, 'telegram_token')
        assert hasattr(settings, 'telegram_chat_id')

    def test_settings_values(self, mock_env_vars):
        """Т значений настроек."""
        assert settings.alerts_api_token == "test_api_token"
        assert settings.telegram_token == "test_token"
        assert settings.telegram_chat_id == "123456789"


class TestServices:
    """Тесты сервисов."""

    def test_alerts_api_service_creation(self, mock_env_vars):
        """Т создания сервиса API."""
        service = AlertsApiService()
        assert service is not None
        assert hasattr(service, 'session')
        assert service.settings is not None

    def test_telegram_service_creation(self, mock_env_vars):
        """Т создания сервиса Telegram."""
        service = TelegramService()
        assert service is not None
        assert service.settings is not None
        assert service.is_enabled is True  # Когда токен установлен

    def test_telegram_service_disabled(self):
        """Т сервиса Telegram без токена."""
        with patch.dict(os.environ, {"TELEGRAM_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            # Пересоздаем настройки
            from importlib import reload
            import config
            reload(config)

            service = TelegramService()
            assert service.is_enabled is False

    def test_task_scheduler_creation(self, mock_env_vars):
        """Т создания планировщика задач."""
        alerts_service = AlertsApiService()
        telegram_service = TelegramService()

        scheduler = TaskScheduler(alerts_service, telegram_service)
        assert scheduler is not None
        assert scheduler.alerts_service is not None
        assert scheduler.telegram_service is not None


class TestAPIEndpoints:
    """Тесты API эндпоинтов."""

    def test_health_check(self):
        """Т проверки здоровья."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_metrics_endpoint(self):
        """Т эндпоинта метрик."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_status_endpoint(self):
        """Т эндпоинта статуса."""
        response = client.get("/status")
        # Должен вернуть данные или пустой объект
        assert response.status_code == 200
        assert isinstance(response.json(), dict)

    def test_debug_services_endpoint(self, mock_env_vars):
        """Т отладочного эндпоинта сервисов."""
        response = client.get("/debug/services")
        assert response.status_code == 200

        data = response.json()
        assert "alerts_service" in data
        assert "telegram_service" in data
        assert "scheduler" in data

    def test_debug_services_endpoint_production(self):
        """Т что debug эндпоинт отключен в production."""
        with patch.object(settings, 'cors_origins', ['https://example.com']):
            response = client.get("/debug/services")
            assert response.status_code == 200
            assert "error" in response.json()


class TestErrorHandling:
    """Тесты обработки ошибок."""

    def test_404_handling(self):
        """Т обработки 404 ошибки."""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self):
        """Т ошибки метода не разрешен."""
        response = client.post("/status")
        assert response.status_code == 405


class TestMiddleware:
    """Тесты middleware."""

    def test_cors_headers(self):
        """Т CORS заголовков."""
        response = client.options("/status")
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_rate_limiting(self):
        """Т ограничения частоты запросов."""
        # Делаем несколько запросов подряд
        responses = []
        for _ in range(5):
            response = client.get("/status")
            responses.append(response)

        # Первые запросы должны быть успешными
        assert all(r.status_code == 200 for r in responses)


class TestIntegration:
    """Интеграционные тесты."""

    def test_full_application_startup(self, mock_env_vars):
        """Т полного запуска приложения."""
        # Создаем новое приложение
        test_app = create_application()

        # Проверяем что все компоненты инициализированы
        assert test_app is not None

        test_client = TestClient(test_app)

        # Базовые эндпоинты должны работать
        health_response = test_client.get("/health")
        assert health_response.status_code == 200

        debug_response = test_client.get("/debug/services")
        assert debug_response.status_code == 200

    @patch('main.get_alerts_service')
    @patch('main.get_telegram_service')
    def test_service_integration(self, mock_telegram, mock_alerts, mock_env_vars):
        """Т интеграции сервисов."""
        from main import get_scheduler

        # Мокаем сервисы
        mock_alerts.return_value = Mock(spec=AlertsApiService)
        mock_telegram.return_value = Mock(spec=TelegramService)

        # Создаем планировщик
        scheduler = get_scheduler()
        assert scheduler is not None

        # Проверяем что сервисы были запрошены
        mock_alerts.assert_called_once()
        mock_telegram.assert_called_once()


class TestConcurrency:
    """Тесты параллельной работы."""

    def test_concurrent_requests(self):
        """Т параллельных запросов."""
        import concurrent.futures

        def make_request():
            return client.get("/health")

        # Делаем несколько параллельных запросов
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            responses = [future.result() for future in futures]

        # Все запросы должны быть успешными
        for response in responses:
            assert response.status_code == 200


class TestConfigurationLoading:
    """Тесты загрузки конфигурации."""

    def test_environment_variables_loading(self, mock_env_vars):
        """Т загрузки переменных окружения."""
        assert settings.alerts_api_token == "test_api_token"
        assert settings.telegram_token == "test_token"
        assert settings.telegram_chat_id == "123456789"

    def test_default_values(self):
        """Т значений по умолчанию."""
        # Проверяем что значения по умолчанию установлены
        assert hasattr(settings, 'alerts_api_url')
        assert settings.alerts_api_url is not None


class TestDocumentation:
    """Тесты документации."""

    def test_openapi_docs(self):
        """Т документации OpenAPI."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json(self):
        """Т OpenAPI схемы."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema


# Фикстуры для тестов
@pytest.fixture
def mock_env_vars():
    """Фикстура для мокирования переменных окружения."""
    env_vars = {
        "ALERTS_API_TOKEN": "test_api_token",
        "TELEGRAM_TOKEN": "test_token",
        "TELEGRAM_CHAT_ID": "123456789",
        "CORS_ORIGINS": "*"
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def sample_alerts_data():
    """Фикстура с примерными данными тревог."""
    return {
        "Автономна Республіка Крим": False,
        "Волинська область": True,
        "Вінницька область": False,
        "м. Київ": True
    }


class TestBusinessLogic:
    """Тесты бизнес-логики."""

    def test_alerts_data_validation(self, sample_alerts_data):
        """Т валидации данных тревог."""
        from models.alert import RegionStatus

        # Создаем модель для проверки
        for region_name, is_alert in sample_alerts_data.items():
            status = RegionStatus(
                region_name=region_name,
                is_alert=is_alert,
                alert_type="active" if is_alert else "inactive"
            )
            assert status.region_name == region_name
            assert status.is_alert == is_alert

    @patch('services.alerts_api.requests.Session.get')
    def test_api_service_request_format(self, mock_get, mock_env_vars):
        """Т формата запросов к API."""
        mock_response = Mock()
        mock_response.text = "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        service = AlertsApiService()
        result = service.get_alerts_status()

        # Проверяем что запрос был отправлен правильно
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "Authorization" in call_args[1]["headers"]
        assert "Bearer test_api_token" in call_args[1]["headers"]["Authorization"]