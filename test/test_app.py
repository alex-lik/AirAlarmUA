"""Application and API tests for AirAlarmUA."""

import concurrent.futures
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from config import settings
from main import app, create_application
from models.alert import RegionStatus
from services.alerts_api import AlertsApiService
from services.task_scheduler import TaskScheduler
from services.telegram_service import TelegramService

client = TestClient(app)


class TestApplicationCreation:
    """Tests for application factory."""

    def test_create_application(self):
        app_instance = create_application()
        assert app_instance is not None
        assert hasattr(app_instance, "router")

    def test_app_metadata(self):
        assert app is not None
        assert app.title == "AirAlarmUA API"


class TestConfiguration:
    """Tests for application settings."""

    def test_settings_exist(self):
        assert settings is not None
        assert hasattr(settings, "alerts_api_token")
        assert hasattr(settings, "telegram_token")
        assert hasattr(settings, "telegram_chat_id")

    def test_default_values(self):
        assert settings.alerts_api_url is not None
        assert "alerts.in.ua" in settings.alerts_api_url


class TestServices:
    """Tests for service wiring."""

    def test_alerts_api_service_creation(self, mock_env_vars):
        service = AlertsApiService()
        assert service is not None
        assert hasattr(service, "session")
        assert service.settings is not None

    def test_telegram_service_creation(self, mock_env_vars):
        service = TelegramService()
        assert service is not None
        assert service.settings is not None

    def test_task_scheduler_creation(self, mock_env_vars):
        scheduler = TaskScheduler(AlertsApiService(), TelegramService())
        assert scheduler.alerts_service is not None
        assert scheduler.telegram_service is not None
        assert scheduler.is_running is False
        assert scheduler.failure_count == 0


class TestAPIEndpoints:
    """Tests for HTTP endpoints."""

    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] in ["healthy", "unhealthy"]

    def test_metrics_endpoint(self):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_status_endpoint(self):
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        assert isinstance(response.json(), dict)

    def test_debug_services_endpoint(self):
        response = client.get("/debug/services")
        assert response.status_code == 200
        data = response.json()
        assert "alerts_service" in data
        assert "telegram_service" in data
        assert "scheduler" in data

    def test_debug_services_disabled_in_production(self):
        with patch.object(settings, "cors_origins", ["https://example.com"]):
            response = client.get("/debug/services")
            assert response.status_code == 200
            assert "error" in response.json()


class TestErrorHandling:
    """Tests for error responses."""

    def test_404_handling(self):
        assert client.get("/nonexistent").status_code == 404

    def test_method_not_allowed(self):
        assert client.post("/api/v1/status").status_code == 405


class TestConcurrency:
    """Tests for concurrent requests."""

    def test_concurrent_health_checks(self):
        def make_request():
            return client.get("/health")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            responses = list(executor.map(lambda _: make_request(), range(10)))

        assert all(r.status_code == 200 for r in responses)


class TestDocumentation:
    """Tests for OpenAPI docs."""

    def test_openapi_docs(self):
        assert client.get("/docs").status_code == 200

    def test_openapi_json(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema


@pytest.fixture
def sample_alerts_data():
    return {
        "Автономна Республіка Крим": False,
        "Волинська область": True,
        "Вінницька область": False,
        "м. Київ": True,
    }


class TestBusinessLogic:
    """Tests for domain models."""

    def test_alerts_data_validation(self, sample_alerts_data):
        for region_name, is_alert in sample_alerts_data.items():
            status = RegionStatus(
                region_name=region_name,
                is_alert=is_alert,
                alert_type="active" if is_alert else "inactive",
            )
            assert status.region_name == region_name
            assert status.is_alert == is_alert

    @pytest.mark.asyncio
    @patch("services.alerts_api.requests.Session.get")
    async def test_api_service_request(self, mock_get, mock_env_vars):
        mock_response = Mock()
        mock_response.text = "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        service = AlertsApiService()
        result = await service.get_alerts_status()

        mock_get.assert_called_once()
        assert result is not None
