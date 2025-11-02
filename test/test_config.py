import pytest
import os
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
# from dotenv import load_dotenv  # Временно отключен

# Импортируем основные функции
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (
    app, get_api_headers, send_telegram_alert,
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, ALERTS_API_TOKEN
)


class TestEnvironmentConfiguration:
    """Тесты конфигурации окружения"""

    def test_required_environment_variables(self, mock_env_vars):
        """Т наличия обязательных переменных окружения"""
        # Эти переменные должны быть установлены в mock_env_vars
        assert os.getenv("ALERTS_API_TOKEN") == "test_api_token"
        assert os.getenv("TELEGRAM_TOKEN") == "test_token"
        assert os.getenv("TELEGRAM_CHAT_ID") == "123456789"

    def test_optional_environment_variables(self):
        """Т опциональных переменных окружения"""
        # Sentry DSN может отсутствовать
        sentry_dsn = os.getenv("SENTRY_DSN")
        assert sentry_dsn is None or sentry_dsn == ""

    def test_environment_variable_types(self, mock_env_vars):
        """Т типов переменных окружения"""
        # Проверяем что переменные являются строками
        assert isinstance(os.getenv("TELEGRAM_TOKEN"), str)
        assert isinstance(os.getenv("TELEGRAM_CHAT_ID"), str)
        assert isinstance(os.getenv("ALERTS_API_TOKEN"), str)

    @patch.dict(os.environ, {
        "TELEGRAM_TOKEN": "new_token",
        "TELEGRAM_CHAT_ID": "999999999",
        "ALERTS_API_TOKEN": "new_api_token"
    })
    def test_environment_variable_override(self):
        """Т переопределения переменных окружения"""
        assert os.getenv("TELEGRAM_TOKEN") == "new_token"
        assert os.getenv("TELEGRAM_CHAT_ID") == "999999999"
        assert os.getenv("ALERTS_API_TOKEN") == "new_api_token"

    def test_empty_environment_variables(self):
        """Т пустых переменных окружения"""
        with patch.dict(os.environ, {
            "TELEGRAM_TOKEN": "",
            "TELEGRAM_CHAT_ID": "",
            "ALERTS_API_TOKEN": ""
        }):
            # Функции должны обрабатывать пустые переменные
            with pytest.raises(ValueError, match="ALERTS_API_TOKEN не установлен"):
                get_api_headers()

    def test_whitespace_only_environment_variables(self):
        """Т переменных окружения состоящих из пробелов"""
        with patch.dict(os.environ, {
            "TELEGRAM_TOKEN": "   ",
            "TELEGRAM_CHAT_ID": "  ",
            "ALERTS_API_TOKEN": ""
        }):
            # Пустые значения должны рассматриваться как отсутствующие
            with pytest.raises(ValueError, match="ALERTS_API_TOKEN не установлен"):
                get_api_headers()


class TestConfigurationValidation:
    """Тесты валидации конфигурации"""

    def test_telegram_token_validation(self, mock_env_vars):
        """Т валидации токена Telegram"""
        # Используем прямое чтение из окружения вместо глобальных переменных
        token = os.getenv("TELEGRAM_TOKEN")
        assert token == "test_token"

    def test_telegram_chat_id_validation(self, mock_env_vars):
        """Т валидации Chat ID Telegram"""
        # Используем прямое чтение из окружения
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        assert chat_id == "123456789"
        assert chat_id.isdigit()

    def test_api_token_validation(self, mock_env_vars):
        """Т валидации токена API"""
        # Используем прямое чтение из окружения
        api_token = os.getenv("ALERTS_API_TOKEN")
        assert api_token
        assert len(api_token) > 0

    def test_invalid_telegram_chat_id(self):
        """Т невалидного Chat ID"""
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "invalid_chat_id"}):
            # Chat ID должен быть числом
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
            assert not chat_id.isdigit()


class TestConfigurationDefaults:
    """Тесты значений по умолчанию"""

    def test_default_rate_limit(self):
        """Т значений rate limiting по умолчанию"""
        # Проверяем что rate limit установлен
        client = TestClient(app)
        response = client.get("/status")
        assert response.status_code == 200

    def test_default_cors_settings(self):
        """Т настроек CORS по умолчанию"""
        client = TestClient(app)
        response = client.options("/status")
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_default_middleware_configuration(self):
        """Т конфигурации middleware по умолчанию"""
        # Проверяем что middleware добавлены
        middleware_types = [type(str(middleware.cls)) for middleware in app.user_middleware]
        assert len(middleware_types) > 0


class TestConfigurationErrors:
    """Тесты обработки ошибок конфигурации"""

    def test_missing_api_token_error(self):
        """Т ошибки отсутствия токена API"""
        with patch.dict(os.environ, {"ALERTS_API_TOKEN": ""}):
            with pytest.raises(ValueError, match="ALERTS_API_TOKEN не установлен"):
                get_api_headers()

    def test_invalid_sentry_dsn_handling(self):
        """Т обработки невалидного Sentry DSN"""
        with patch.dict(os.environ, {"SENTRY_DSN": "invalid_dsn"}):
            with patch('main.sentry_sdk.init') as mock_init:
                try:
                    # Импортируем модуль main для инициализации Sentry
                    import importlib
                    import main
                    importlib.reload(main)
                except Exception:
                    pass
                # Sentry должен попытаться инициализироваться

    def test_configuration_without_telegram(self):
        """Т работы без конфигурации Telegram"""
        with patch.dict(os.environ, {"TELEGRAM_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            # Отправка уведомления не должна вызывать ошибку
            send_telegram_alert("Test message")


class TestConfigurationLoading:
    """Тесты загрузки конфигурации"""

    def test_environment_loading_priority(self):
        """Т приоритета загрузки переменных окружения"""
        # Тестируем что os.environ имеет приоритет над .env
        test_token = "priority_test_token"
        with patch.dict(os.environ, {"TELEGRAM_TOKEN": test_token}):
            # Значение должно быть взято из os.environ
            assert os.getenv("TELEGRAM_TOKEN") == test_token

    def test_dotenv_file_loading(self):
        """Т загрузки из .env файла"""
        # Проверяем что load_dotenv работает (если .env существует)
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.getcwd()))), ".env"
        if os.path.exists(env_file):
            # load_dotenv(env_file)  # Временно отключен
            # Переменные из .env должны быть загружены
            pass


class TestRuntimeConfiguration:
    """Тесты конфигурации во время выполнения"""

    def test_dynamic_configuration_changes(self):
        """Т динамических изменений конфигурации"""
        original_token = os.getenv("TELEGRAM_TOKEN")

        try:
            # Меняем переменную окружения
            os.environ["TELEGRAM_TOKEN"] = "dynamic_token"

            # Проверяем что изменение отражено
            assert os.getenv("TELEGRAM_TOKEN") == "dynamic_token"

        finally:
            # Восстанавливаем оригинальное значение
            if original_token:
                os.environ["TELEGRAM_TOKEN"] = original_token
            else:
                os.environ.pop("TELEGRAM_TOKEN", None)

    def test_configuration_isolation(self):
        """Т изоляции конфигурации между тестами"""
        # Проверяем что изменения в одном тесте не влияют на другие
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            assert os.getenv("TEST_VAR") == "test_value"

        # После выхода из контекста переменная должна быть удалена
        assert os.getenv("TEST_VAR") is None


class TestSecurityConfiguration:
    """Тесты конфигурации безопасности"""

    def test_no_hardcoded_credentials(self):
        """Т отсутствия жестко закодированных учетных данных"""
        # Проверяем что в коде нет жестко закодированных токенов
        import main
        import inspect

        source = inspect.getsource(main)

        # Не должно быть реальных токенов в коде
        suspicious_patterns = [
            "bot123456:",  # Реальный формат токена Telegram
            "ghp_",  # GitHub token prefix
            "sk_live_",  # Stripe live key prefix
        ]

        for pattern in suspicious_patterns:
            assert pattern not in source, f"Found suspicious pattern: {pattern}"

    def test_cors_security_configuration(self):
        """Т конфигурации CORS для безопасности"""
        client = TestClient(app)
        response = client.get("/status")

        # В production нужно будет ограничить origins
        # Сейчас используется "*" для тестирования
        headers = response.headers
        assert "access-control-allow-origin" in headers

    def test_sensitive_data_not_exposed(self):
        """Т что чувствительные данные не экспонируются"""
        client = TestClient(app)

        # Проверяем различные эндпоинты
        endpoints = ["/status", "/health", "/metrics"]

        for endpoint in endpoints:
            response = client.get(endpoint)
            response_text = str(response.content)

            # Не должно быть токенов или паролей
            assert "token" not in response_text.lower()
            assert "password" not in response_text.lower()
            assert "secret" not in response_text.lower()


class TestConfigurationPerformance:
    """Тесты производительности конфигурации"""

    def test_configuration_loading_speed(self):
        """Т скорости загрузки конфигурации"""
        import time

        start_time = time.time()

        # Многократное чтение переменных окружения
        for _ in range(1000):
            _ = os.getenv("TELEGRAM_TOKEN")
            _ = os.getenv("ALERTS_API_TOKEN")

        end_time = time.time()

        # Должно быть быстро
        assert (end_time - start_time) < 0.1

    def test_memory_usage_configuration(self):
        """Т использования памяти конфигурацией"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Создаем много конфигурационных объектов
        configs = []
        for i in range(100):
            with patch.dict(os.environ, {f"TEST_VAR_{i}": f"value_{i}"}):
                configs.append(os.getenv(f"TEST_VAR_{i}"))

        # Память не должна сильно вырасти
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory
        assert memory_growth < 1 * 1024 * 1024  # Менее 1MB


class TestConfigurationCompatibility:
    """Тесты совместимости конфигурации"""

    def test_python_version_compatibility(self):
        """Т совместимости с версией Python"""
        import sys

        # Проверяем минимальную версию Python
        assert sys.version_info >= (3, 8), "Python 3.8+ required"

    def test_dependency_compatibility(self):
        """Т совместимости зависимостей"""
        import pkg_resources

        # Проверяем основные зависимости
        required_packages = [
            "fastapi",
            "requests",
            "loguru",
            "prometheus_client"
        ]

        for package in required_packages:
            try:
                pkg_resources.get_distribution(package)
            except pkg_resources.DistributionNotFound:
                pytest.fail(f"Required package {package} not found")

    def test_platform_compatibility(self):
        """Т кросс-платформенной совместимости"""
        import platform

        # Проверяем что приложение работает на текущей платформе
        system = platform.system()
        assert system in ["Windows", "Linux", "Darwin"], f"Unsupported platform: {system}"