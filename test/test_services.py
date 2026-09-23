"""Service-level tests for AirAlarmUA."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from config import REGIONS_UID_MAP, settings
from main import create_application
from models.alert import AlertStatus, AlertSystemStatus, RegionStatus
from services.alerts_api import AlertsApiService
from services.task_scheduler import TaskScheduler
from services.telegram_service import TelegramService
from utils.logger import get_logger
from utils.metrics import metrics_collector


class TestServiceWiring:
    """Tests for service creation and wiring."""

    def test_services_creation(self):
        alerts_service = AlertsApiService()
        telegram_service = TelegramService()
        scheduler = TaskScheduler(alerts_service, telegram_service)

        assert alerts_service is not None
        assert telegram_service is not None
        assert scheduler is not None
        assert scheduler.alerts_service is alerts_service
        assert scheduler.telegram_service is telegram_service

    def test_error_handling_interface(self):
        service = AlertsApiService()
        assert hasattr(service, "_make_request")
        assert hasattr(service, "_fetch_data_with_retry")
        assert hasattr(service, "close")

    def test_scheduler_lifecycle_interface(self):
        scheduler = TaskScheduler(AlertsApiService(), TelegramService())
        assert hasattr(scheduler, "start")
        assert hasattr(scheduler, "stop")
        assert hasattr(scheduler, "is_running")

    def test_configuration_fields(self):
        for field in ["alerts_api_url", "cors_origins"]:
            assert hasattr(settings, field)

    def test_logging_setup(self):
        assert get_logger("test") is not None

    def test_metrics_setup(self):
        assert metrics_collector is not None


class TestRequestHandling:
    """Tests for app request handling."""

    def test_unknown_route_returns_404(self):
        client = TestClient(create_application())
        assert client.get("/nonexistent").status_code == 404

    def test_middleware_configured(self):
        app = create_application()
        assert len(app.user_middleware) > 0


class TestServiceCommunication:
    """Tests for service configuration."""

    def test_alerts_service_headers(self):
        session = AlertsApiService().session
        assert "Authorization" in session.headers
        assert "Content-Type" in session.headers

    def test_telegram_service_settings(self):
        assert TelegramService().settings is not None

    def test_scheduler_initial_state(self):
        scheduler = TaskScheduler(AlertsApiService(), TelegramService())
        assert scheduler.is_running is False
        assert scheduler.failure_count == 0

    def test_alerts_service_mock(self):
        with patch("services.alerts_api.requests.Session.get") as mock_get:
            mock_response = Mock()
            mock_response.text = "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            service = AlertsApiService()
            assert service.session is not None


class TestDataValidation:
    """Tests for domain data structures."""

    def test_status_data_structure(self):
        regions = {
            "Київська область": RegionStatus(
                region_name="Київська область",
                is_alert=True,
                alert_type=AlertStatus.ACTIVE,
                last_updated=datetime.utcnow(),
            ),
        }
        status = AlertSystemStatus(
            regions=regions,
            total_regions=1,
            active_alerts=1,
            last_update=datetime.utcnow(),
            api_status="ok",
        )
        assert status.total_regions == 1
        assert status.active_alerts == 1
        assert status.api_status == "ok"

    def test_region_uid_map(self):
        assert len(REGIONS_UID_MAP) > 0
        assert 1 in REGIONS_UID_MAP
        assert 31 in REGIONS_UID_MAP

    def test_api_url(self):
        assert settings.alerts_api_url.startswith("https://")
        assert "alerts.in.ua" in settings.alerts_api_url
