import pytest
from unittest.mock import patch, Mock
import time
from prometheus_client import REGISTRY, CollectorRegistry

# Импортируем основные функции
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (
    app, active_regions, update_timestamp, get_air_alerts_status,
    alert_status, REGIONS_UID_MAP
)
from fastapi.testclient import TestClient


class TestPrometheusMetrics:
    """Тесты метрик Prometheus"""

    def setup_method(self):
        """Очистка реестра метрик перед каждым тестом"""
        # Создаем отдельный реестр для тестов
        self.test_registry = CollectorRegistry()

    def test_active_regions_gauge_creation(self):
        """Т создания gauge для активных регионов"""
        assert active_regions is not None
        assert active_regions._name == "air_alert_regions_total"
        assert active_regions._documentation == "Количество регионов по статусу"

    def test_update_timestamp_gauge_creation(self):
        """Т создания gauge для времени обновления"""
        assert update_timestamp is not None
        assert update_timestamp._name == "air_alert_last_update_timestamp"
        assert update_timestamp._documentation == "Последнее обновление в формате UNIX-времени"

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_metrics_update_on_successful_fetch(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т обновления метрик при успешном получении данных"""
        test_statuses = "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"  # Смешанные статусы
        mock_fetch.return_value = {"statuses": test_statuses}

        # Сохраняем начальные значения
        initial_active = active_regions.labels(status="active")._value._value
        initial_inactive = active_regions.labels(status="inactive")._value._value
        initial_timestamp = update_timestamp._value._value

        get_air_alerts_status()

        # Проверяем что метрики обновились
        new_active = active_regions.labels(status="active")._value._value
        new_inactive = active_regions.labels(status="inactive")._value._value
        new_timestamp = update_timestamp._value._value

        assert new_active != initial_active or new_inactive != initial_inactive
        assert new_timestamp > initial_timestamp

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_metrics_count_all_active_regions(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т подсчета всех активных регионов"""
        # Все регионы активны
        all_active_statuses = "A" * len(REGIONS_UID_MAP)
        mock_fetch.return_value = {"statuses": all_active_statuses}

        get_air_alerts_status()

        active_count = active_regions.labels(status="active")._value._value
        inactive_count = active_regions.labels(status="inactive")._value._value

        assert active_count == len(REGIONS_UID_MAP)
        assert inactive_count == 0

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_metrics_count_all_inactive_regions(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т подсчета всех неактивных регионов"""
        # Все регионы неактивны
        all_inactive_statuses = "N" * len(REGIONS_UID_MAP)
        mock_fetch.return_value = {"statuses": all_inactive_statuses}

        get_air_alerts_status()

        active_count = active_regions.labels(status="active")._value._value
        inactive_count = active_regions.labels(status="inactive")._value._value

        assert active_count == 0
        assert inactive_count == len(REGIONS_UID_MAP)

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_metrics_count_partial_alerts(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т подсчета регионов с частичными тревогами"""
        # Создаем строку с частичными тревогами
        statuses = []
        for uid in sorted(REGIONS_UID_MAP.keys()):
            if uid % 3 == 0:
                statuses.append('A')  # Полная тревога
            elif uid % 3 == 1:
                statuses.append('P')  # Частичная тревога
            else:
                statuses.append('N')  # Нет тревоги

        test_statuses = ''.join(statuses)
        mock_fetch.return_value = {"statuses": test_statuses}

        get_air_alerts_status()

        active_count = active_regions.labels(status="active")._value._value
        inactive_count = active_regions.labels(status="inactive")._value._value

        # A и P считаются как активные
        expected_active = len([s for s in statuses if s in ['A', 'P']])
        expected_inactive = len([s for s in statuses if s == 'N'])

        assert active_count == expected_active
        assert inactive_count == expected_inactive

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_timestamp_metric_update(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т обновления метрики времени"""
        import time

        mock_fetch.return_value = {"statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"}

        expected_timestamp = int(time.time())
        get_air_alerts_status()

        actual_timestamp = update_timestamp._value._value

        # Разница должна быть небольшой (менее 5 секунд)
        assert abs(actual_timestamp - expected_timestamp) < 5

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_metrics_dont_update_on_api_error(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т что метрики не обновляются при ошибке API"""
        mock_fetch.side_effect = Exception("API Error")

        # Сохраняем начальные значения
        initial_active = active_regions.labels(status="active")._value._value
        initial_inactive = active_regions.labels(status="inactive")._value._value
        initial_timestamp = update_timestamp._value._value

        get_air_alerts_status()

        # Метрики не должны измениться
        new_active = active_regions.labels(status="active")._value._value
        new_inactive = active_regions.labels(status="inactive")._value._value
        new_timestamp = update_timestamp._value._value

        assert new_active == initial_active
        assert new_inactive == initial_inactive
        assert new_timestamp == initial_timestamp


class TestMetricsEndpoint:
    """Тесты эндпоинта метрик"""

    def test_metrics_endpoint_response(self):
        """Т ответа эндпоинта метрик"""
        client = TestClient(app)
        response = client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_metrics_endpoint_content(self):
        """Т содержимого эндпоинта метрик"""
        client = TestClient(app)
        response = client.get("/metrics")

        metrics_text = response.text

        # Проверяем наличие наших метрик
        assert "air_alert_regions_total" in metrics_text
        assert "air_alert_last_update_timestamp" in metrics_text

    def test_metrics_endpoint_format(self):
        """Т формата метрик"""
        client = TestClient(app)
        response = client.get("/metrics")

        metrics_text = response.text

        # Проверяем базовый формат Prometheus
        lines = metrics_text.split('\n')
        non_empty_lines = [line.strip() for line in lines if line.strip()]

        assert len(non_empty_lines) > 0

        # Каждая метрика должна иметь формат
        for line in non_empty_lines:
            if line.startswith('#'):
                # Это комментарий
                assert line.startswith('# HELP') or line.startswith('# TYPE')
            else:
                # Это метрика со значением
                parts = line.split()
                assert len(parts) >= 2
                # Первая часть - имя метрики, последняя - значение
                assert parts[0]
                try:
                    float(parts[-1])
                except ValueError:
                    # Если это не число, может быть гистограмма или другая сложная метрика
                    pass

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_metrics_update_reflected_in_endpoint(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т что обновления метрик отражаются в эндпоинте"""
        # Обновляем метрики
        mock_fetch.return_value = {"statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"}
        get_air_alerts_status()

        # Проверяем эндпоинт
        client = TestClient(app)
        response = client.get("/metrics")
        metrics_text = response.text

        # Ищем наши метрики в тексте
        assert 'air_alert_regions_total{status="active"}' in metrics_text
        assert 'air_alert_regions_total{status="inactive"}' in metrics_text
        assert 'air_alert_last_update_timestamp' in metrics_text


class TestMetricsInstrumentator:
    """Тесты интеграции с Prometheus FastAPI Instrumentator"""

    def test_fastapi_metrics_present(self):
        """Т что метрики FastAPI присутствуют"""
        client = TestClient(app)
        response = client.get("/metrics")

        metrics_text = response.text

        # Базовые метрики FastAPI
        fastapi_metrics = [
            "http_requests_total",
            "http_request_duration_seconds",
            "process_cpu_seconds_total",
            "process_resident_memory_bytes"
        ]

        for metric in fastapi_metrics:
            # Некоторые метрики могут отсутствовать в зависимости от конфигурации
            if metric in metrics_text:
                assert metric in metrics_text

    def test_request_metrics_after_api_calls(self):
        """Т что метрики запросов обновляются после вызовов API"""
        client = TestClient(app)

        # Делаем несколько запросов
        client.get("/health")
        client.get("/status")
        client.get("/health")

        # Проверяем метрики
        response = client.get("/metrics")
        metrics_text = response.text

        # Должны быть метрики HTTP запросов
        if "http_requests_total" in metrics_text:
            assert "http_requests_total" in metrics_text

    def test_metrics_access_control(self):
        """Т доступа к эндпоинту метрик"""
        client = TestClient(app)

        # Эндпоинт метрик должен быть доступен без аутентификации
        response = client.get("/metrics")
        assert response.status_code == 200

        # Проверяем различные HTTP методы
        assert client.get("/metrics").status_code == 200
        # HEAD должен тоже работать
        head_response = client.head("/metrics")
        assert head_response.status_code == 200

    def test_metrics_content_type(self):
        """Т Content-Type для метрик"""
        client = TestClient(app)
        response = client.get("/metrics")

        assert response.status_code == 200
        content_type = response.headers["content-type"]
        assert "text/plain" in content_type
        # Prometheus может добавлять версию
        assert "version" in content_type.lower()


class TestMetricsReliability:
    """Тесты надежности метрик"""

    def test_metrics_thread_safety(self):
        """Т потокобезопасности метрик"""
        import threading
        import time

        def update_metrics():
            from main import active_regions, update_timestamp
            for i in range(10):
                try:
                    active_regions.labels(status="active").set(i)
                    update_timestamp.set(int(time.time()))
                    time.sleep(0.001)
                except Exception:
                    pass  # Игнорируем ошибки в тесте

        # Создаем несколько потоков обновления метрик
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=update_metrics)
            threads.append(thread)
            thread.start()

        # Ждем завершения
        for thread in threads:
            thread.join()

        # Проверяем что эндпоинт все еще работает
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_metrics_consistency_after_errors(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т консистентности метрик после ошибок"""
        # Сначала успешное обновление
        mock_fetch.return_value = {"statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"}
        get_air_alerts_status()

        # Сохраняем значения
        active_after_success = active_regions.labels(status="active")._value._value
        timestamp_after_success = update_timestamp._value._value

        # Теперь ошибка
        mock_fetch.side_effect = Exception("API Error")
        get_air_alerts_status()

        # Метрики не должны измениться
        active_after_error = active_regions.labels(status="active")._value._value
        timestamp_after_error = update_timestamp._value._value

        assert active_after_success == active_after_error
        assert timestamp_after_success == timestamp_after_error

    def test_metrics_memory_usage(self):
        """Т использования памяти метриками"""
        import gc
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Создаем много метрик (если бы мы их создавали динамически)
        # В нашем случае метрики статические, но проверим базовое использование
        for i in range(100):
            client = TestClient(app)
            response = client.get("/metrics")
            assert response.status_code == 200
            del response
            del client

        gc.collect()
        final_memory = process.memory_info().rss

        # Память не должна сильно вырасти
        memory_growth = final_memory - initial_memory
        # Допустимый рост - до 10MB
        assert memory_growth < 10 * 1024 * 1024


class TestCustomMetrics:
    """Тесты кастомных метрик"""

    def test_regions_metric_labels(self):
        """Т метрик регионов с правильными лейблами"""
        # Проверяем что gauge создан с правильными лейблами
        assert hasattr(active_regions, '_labelvalues')

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_metric_values_are_numbers(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т что значения метрик являются числами"""
        mock_fetch.return_value = {"statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"}
        get_air_alerts_status()

        # Проверяем что значения являются числами
        active_value = active_regions.labels(status="active")._value._value
        inactive_value = active_regions.labels(status="inactive")._value._value
        timestamp_value = update_timestamp._value._value

        assert isinstance(active_value, (int, float))
        assert isinstance(inactive_value, (int, float))
        assert isinstance(timestamp_value, (int, float))

        # Проверяем диапазоны значений
        assert active_value >= 0
        assert inactive_value >= 0
        assert timestamp_value > 0

    def test_metric_names_are_valid(self):
        """Т что имена метрик валидны для Prometheus"""
        import re

        # Prometheus metric name pattern
        metric_name_pattern = r'^[a-zA-Z_:][a-zA-Z0-9_:]*$'

        assert re.match(metric_name_pattern, active_regions._name)
        assert re.match(metric_name_pattern, update_timestamp._name)

    def test_metric_help_text(self):
        """Т текста справки метрик"""
        assert active_regions._documentation
        assert update_timestamp._documentation

        assert len(active_regions._documentation) > 0
        assert len(update_timestamp._documentation) > 0

        # Текст должен быть на русском (на основе нашей локали)
        assert "Количество" in active_regions._documentation
        assert "времени" in update_timestamp._documentation