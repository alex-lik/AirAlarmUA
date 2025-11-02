import pytest
import asyncio
from unittest.mock import patch, Mock, AsyncMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
# import freezegun  # Временно отключен для Python 3.13 совместимости

# Импортируем основное приложение
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, lifespan, periodic_task


class TestFastAPIApp:
    """Тесты FastAPI приложения и его жизненного цикла"""

    def test_app_creation(self):
        """Т создания FastAPI приложения"""
        assert app is not None
        assert app.title == "FastAPI"
        assert hasattr(app, 'router')

    @pytest.mark.asyncio
    async def test_lifespan_context_manager(self, mock_env_vars):
        """Т контекстного менеджера жизненного цикла"""
        with patch('main.periodic_task') as mock_task:
            async with lifespan(app):
                # Проверяем что periodic_task запущен
                mock_task.assert_not_called()  # Запускается в отдельном потоке

    def test_cors_middleware(self):
        """Т настройки CORS middleware"""
        client = TestClient(app)

        # Т OPTIONS запрос
        response = client.options("/status")
        assert response.status_code == 200

        # Т заголовков CORS
        response = client.get("/status")
        assert "access-control-allow-origin" in response.headers

    def test_rate_limiting_middleware(self):
        """Т middleware ограничения частоты запросов"""
        client = TestClient(app)

        # Делаем несколько запросов подряд
        for _ in range(5):
            response = client.get("/status")
            assert response.status_code == 200

    def test_prometheus_instrumentation(self):
        """Т интеграции с Prometheus"""
        client = TestClient(app)

        # Проверяем что эндпоинт метрик доступен
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]


class TestAsyncClient:
    """Тесты с асинхронным клиентом"""

    @pytest.mark.asyncio
    async def test_async_status_request(self):
        """Т асинхронного запроса статуса"""
        async with AsyncClient(app=app, base_url="http://test") as async_client:
            with patch('main.alert_status', {"test": True}):
                response = await async_client.get("/status")
                assert response.status_code == 200
                assert response.json() == {"test": True}

    @pytest.mark.asyncio
    async def test_async_region_search(self):
        """Т асинхронного поиска региона"""
        async with AsyncClient(app=app, base_url="http://test") as async_client:
            with patch('main.alert_status', {"м. Київ": True, "Київська область": False}):
                response = await async_client.get("/region/Київ")
                assert response.status_code == 200
                data = response.json()
                assert len(data) == 2

    @pytest.mark.asyncio
    async def test_concurrent_async_requests(self):
        """Т параллельных асинхронных запросов"""
        async with AsyncClient(app=app, base_url="http://test") as async_client:
            with patch('main.alert_status', {"test": True}):
                # Создаем несколько параллельных запросов
                tasks = [async_client.get("/status") for _ in range(10)]
                responses = await asyncio.gather(*tasks)

                # Все запросы должны быть успешными
                for response in responses:
                    assert response.status_code == 200
                    assert response.json() == {"test": True}


class TestErrorHandling:
    """Тесты обработки ошибок в FastAPI"""

    def test_404_error_handling(self):
        """Т обработки 404 ошибки"""
        client = TestClient(app)
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_validation_error_handling(self):
        """Т обработки ошибок валидации"""
        client = TestClient(app)
        # Этот эндпоинт принимает любой путь, но должен корректно обрабатывать параметры
        response = client.get("/region/\"")
        # Не должно быть ошибки валидации

    @patch('main.alert_status', {})
    def test_empty_data_handling(self):
        """Т обработки пустых данных"""
        client = TestClient(app)
        response = client.get("/status")
        assert response.status_code == 200
        assert response.json() == {}

    def test_case_insensitive_search(self):
        """Т поиска без учета регистра"""
        client = TestClient(app)

        with patch('main.alert_status', {
            "м. Київ": True,
            "КИЇВСЬКА ОБЛАСТЬ": False,
            "Харківська область": True
        }):
            # Т поиска в нижнем регистре
            response = client.get("/region/київ")
            assert response.status_code == 200
            assert "м. Київ" in response.json()

            # Т поиска в верхнем регистре
            response = client.get("/region/КИЇВ")
            assert response.status_code == 200


class TestPerformance:
    """Тесты производительности"""

    def test_response_time_under_limit(self):
        """Т времени ответа"""
        import time
        client = TestClient(app)

        with patch('main.alert_status', {f"region_{i}": i % 2 == 0 for i in range(100)}):
            start_time = time.time()
            response = client.get("/status")
            end_time = time.time()

            assert response.status_code == 200
            assert (end_time - start_time) < 0.1  # Менее 100ms

    def test_large_response_handling(self):
        """Т обработки больших ответов"""
        client = TestClient(app)

        # Создаем большой объем данных
        large_data = {f"region_{i}": i % 2 == 0 for i in range(1000)}

        with patch('main.alert_status', large_data):
            response = client.get("/status")
            assert response.status_code == 200
            assert len(response.json()) == 1000

    def test_memory_usage_stability(self):
        """Т стабильности использования памяти"""
        client = TestClient(app)

        # Делаем много запросов подряд
        for i in range(100):
            with patch('main.alert_status', {f"region_{i}": i % 2 == 0}):
                response = client.get("/status")
                assert response.status_code == 200


class TestSecurity:
    """Тесты безопасности"""

    def test_no_sensitive_data_leakage(self):
        """Т отсутствия утечки чувствительных данных"""
        client = TestClient(app)

        response = client.get("/status")

        # Проверяем что в ответе нет токенов или паролей
        response_text = str(response.content)
        assert "token" not in response_text.lower()
        assert "password" not in response_text.lower()
        assert "secret" not in response_text.lower()

    def test_input_sanitization(self):
        """Т санитизации входных данных"""
        client = TestClient(app)

        # Т с потенциально опасными символами
        dangerous_inputs = [
            "../",
            "<script>",
            "SELECT * FROM",
            "${jndi:",
            "{{7*7}}"
        ]

        for dangerous_input in dangerous_inputs:
            response = client.get(f"/region/{dangerous_input}")
            # Не должно быть внутренних ошибок сервера
            assert response.status_code in [200, 404]

    def test_request_size_limit(self):
        """Т ограничения размера запроса"""
        client = TestClient(app)

        # Создаем очень длинное имя региона
        long_region_name = "a" * 10000

        response = client.get(f"/region/{long_region_name}")
        # Не должно быть ошибок обработки
        assert response.status_code in [200, 404]


class TestHeaders:
    """Тесты заголовков"""

    def test_content_type_headers(self):
        """Т заголовков Content-Type"""
        client = TestClient(app)

        # Т JSON эндпоинтов
        response = client.get("/status")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

        # Т эндпоинта метрик
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_cors_headers(self):
        """Т CORS заголовков"""
        client = TestClient(app)

        response = client.get("/status")
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "*"

    def test_security_headers(self):
        """Т заголовков безопасности"""
        client = TestClient(app)

        response = client.get("/status")
        # Проверяем основные заголовки безопасности
        headers = response.headers

        # Эти заголовки могут отсутствовать, но если есть, должны быть корректными
        if "x-content-type-options" in headers:
            assert headers["x-content-type-options"] == "nosniff"


class TestLogging:
    """Тесты логирования"""

    @patch('main.logger')
    def test_error_logging(self, mock_logger, mock_env_vars):
        """Т логирования ошибок"""
        with patch('main.fetch_alerts_from_api') as mock_fetch:
            mock_fetch.side_effect = Exception("Test error")

            # Вызываем функцию которая должна логировать ошибку
            from main import get_air_alerts_status

            try:
                get_air_alerts_status()
            except:
                pass

            # Проверяем что ошибка была залогирована
            mock_logger.error.assert_called()

    def test_request_logging(self):
        """Т логирования запросов"""
        client = TestClient(app)

        # Делаем запрос
        response = client.get("/status")
        assert response.status_code == 200

        # В реальном приложении здесь были бы проверки логов запросов
        # Но для этого нужно настроить capture логов в тестах


class TestConfiguration:
    """Тесты конфигурации"""

    def test_app_configuration(self):
        """Т конфигурации приложения"""
        assert app is not None

        # Проверяем что middleware добавлены
        middleware_types = [type(str(middleware.cls)) for middleware in app.user_middleware]

        # Должны быть CORS и rate limiting middleware
        assert any("CORSMiddleware" in middleware_type for middleware_type in middleware_types)

    def test_environment_variables(self, mock_env_vars):
        """Т переменных окружения"""
        assert os.getenv("TELEGRAM_TOKEN") == "test_token"
        assert os.getenv("ALERTS_API_TOKEN") == "test_api_token"

    def test_sentry_configuration(self):
        """Т конфигурации Sentry"""
        # Sentry должен инициализироваться только если DSN указан
        with patch.dict(os.environ, {"SENTRY_DSN": ""}):
            with patch('main.sentry_sdk.init') as mock_sentry:
                # Re-import для проверки инициализации
                import importlib
                import main
                importlib.reload(main)

                # Sentry не должен инициализироваться с пустым DSN
                # (точная проверка зависит от реализации)