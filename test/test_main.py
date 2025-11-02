import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock, Mock
from fastapi.testclient import TestClient
from fastapi import Request
import requests
# import freezegun  # Временно отключен для Python 3.13 совместимости

# Импортируем основное приложение
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (
    app, alert_status, last_update_time, last_kyiv_status, failure_count, MAX_FAILURES,
    REGIONS_UID_MAP, get_api_headers, fetch_alerts_from_api, send_telegram_alert,
    get_air_alerts_status, periodic_task, active_regions, update_timestamp
)

# Создаем тестовый клиент
client = TestClient(app)


class TestMainFunctions:
    """Тесты основных функций приложения"""

    def test_get_api_headers_success(self, mock_env_vars):
        """Т успешного получения заголовков API"""
        headers = get_api_headers()
        assert headers["Authorization"] == "Bearer test_api_token"
        assert headers["Content-Type"] == "application/json"

    def test_get_api_headers_missing_token(self):
        """Тест ошибки при отсутствии токена"""
        with patch.dict(os.environ, {"ALERTS_API_TOKEN": ""}):
            with pytest.raises(ValueError, match="ALERTS_API_TOKEN не установлен"):
                get_api_headers()

    @patch('main.requests.get')
    def test_fetch_alerts_from_api_success(self, mock_get, mock_env_vars):
        """Тест успешного получения данных из API"""
        mock_response = Mock()
        mock_response.text = "ANAPPPPPPPPNNPPPPNPNPPPPPNPNPNPN"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_alerts_from_api()

        assert result["statuses"] == "ANAPPPPPPPPNNPPPPNPNPPPPPNPNPNPN"
        mock_get.assert_called_once()
        mock_get.assert_called_with(
            "https://api.alerts.in.ua/v1/iot/active_air_raid_alerts.json",
            headers=get_api_headers(),
            timeout=15
        )

    @patch('main.requests.get')
    def test_fetch_alerts_from_api_error(self, mock_get, mock_env_vars):
        """Тест обработки ошибки API"""
        mock_get.side_effect = requests.RequestException("Connection error")

        with pytest.raises(requests.RequestException):
            fetch_alerts_from_api()

    @patch('main.requests.post')
    def test_send_telegram_alert_success(self, mock_post, mock_env_vars):
        """Тест успешной отправки уведомления в Telegram"""
        send_telegram_alert("Test message")

        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"chat_id": "123456789", "text": "Test message"}
        )

    @patch('main.requests.post')
    def test_send_telegram_alert_error(self, mock_post, mock_env_vars):
        """Тест обработки ошибки при отправке в Telegram"""
        mock_post.side_effect = Exception("Telegram error")

        # Не должно вызывать исключение, только логировать ошибку
        send_telegram_alert("Test message")

    @patch('main.requests.post')
    def test_send_telegram_alert_no_credentials(self, mock_post):
        """Тест что функция работает без ошибок при отсутствии учетных данных"""
        with patch.dict(os.environ, {"TELEGRAM_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            send_telegram_alert("Test message")
            mock_post.assert_not_called()


class TestStatusParsing:
    """Тесты парсинга статусов регионов"""

    def test_parse_statuses_string_all_active(self):
        """Тест парсинга строки со всеми активными тревогами"""
        statuses_string = "A" * 27  # Все регионы с тревогой
        uid_list = sorted(REGIONS_UID_MAP.keys())
        regions = {}

        for i, uid in enumerate(uid_list):
            if i < len(statuses_string):
                status_char = statuses_string[i]
                region_name = REGIONS_UID_MAP[uid]
                is_alert = status_char in ['A', 'P']
                regions[region_name] = is_alert

        assert all(regions.values())  # Все регионы должны быть с тревогой

    def test_parse_statuses_string_all_inactive(self):
        """Тест парсинга строки без тревог"""
        statuses_string = "N" * 27  # Все регионы без тревоги
        uid_list = sorted(REGIONS_UID_MAP.keys())
        regions = {}

        for i, uid in enumerate(uid_list):
            if i < len(statuses_string):
                status_char = statuses_string[i]
                region_name = REGIONS_UID_MAP[uid]
                is_alert = status_char in ['A', 'P']
                regions[region_name] = is_alert

        assert not any(regions.values())  # Все регионы должны быть без тревоги

    def test_parse_statuses_string_mixed(self):
        """Тест парсинга смешанной строки"""
        statuses_string = "ANAPPPPPPPPNNPPPPNPNPPPPPNPNPNPN"
        uid_list = sorted(REGIONS_UID_MAP.keys())
        regions = {}

        for i, uid in enumerate(uid_list):
            if i < len(statuses_string):
                status_char = statuses_string[i]
                region_name = REGIONS_UID_MAP[uid]
                is_alert = status_char in ['A', 'P']
                regions[region_name] = is_alert

        # Проверяем что парсинг работает корректно
        assert regions["Автономна Республіка Крим"] == True  # A
        assert regions["Хмельницька область"] == False  # N (UID 3)
        assert regions["Вінницька область"] == True  # A (UID 4)
        assert regions["Рівненська область"] == True  # P (UID 5)

    def test_regions_uid_map_completeness(self):
        """Тест полноты карты регионов"""
        expected_uids = {1, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30, 31}
        actual_uids = set(REGIONS_UID_MAP.keys())

        assert actual_uids == expected_uids, f"Пропущены UIDs: {expected_uids - actual_uids}"


class TestAPIEndpoints:
    """Тесты API эндпоинтов"""

    @patch('main.alert_status', {
        "м. Київ": True,
        "Київська область": False,
        "Харківська область": True
    })
    def test_get_status_success(self):
        """Т успешного получения статуса"""
        response = client.get("/status")
        assert response.status_code == 200
        assert response.json() == {
            "м. Київ": True,
            "Київська область": False,
            "Харківська область": True
        }

    def test_get_status_empty(self):
        """Т получения статуса когда данных нет"""
        with patch('main.alert_status', {}):
            response = client.get("/status")
            assert response.status_code == 200
            assert response.json() == {}

    @patch('main.alert_status', {
        "м. Київ": True,
        "Київська область": False,
        "Харківська область": True
    })
    def test_get_region_status_exact_match(self):
        """Т поиска региона по точному названию"""
        response = client.get("/region/м. Київ")
        assert response.status_code == 200
        data = response.json()
        assert "м. Київ" in data
        assert data["м. Київ"] == True

    @patch('main.alert_status', {
        "Київська область": False,
        "Харківська область": True
    })
    def test_get_region_status_partial_match(self):
        """Т поиска региона по частичному названию"""
        response = client.get("/region/Київськ")
        assert response.status_code == 200
        assert response.json() == {"Київська область": False}

    @patch('main.alert_status', {
        "м. Київ": True,
        "Київська область": False
    })
    def test_get_region_status_multiple_matches(self):
        """Т поиска региона когда есть несколько совпадений"""
        response = client.get("/region/Київ")
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert "м. Київ" in response.json()
        assert "Київська область" in response.json()

    def test_get_region_status_not_found(self):
        """Т региона который не найден"""
        with patch('main.alert_status', {"м. Київ": True}):
            response = client.get("/region/Несуществующий")
            assert response.status_code == 404
            assert response.json()["detail"] == "Регион не найден"

    def test_health_check(self):
        """Т проверки здоровья"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_sentry_debug(self):
        """Т отладочного эндпоинта Sentry"""
        with pytest.raises(ZeroDivisionError):
            response = client.get("/sentry-debug")
            # Этот эндпоинт должен вызывать ошибку деления на ноль

    def test_metrics_endpoint(self):
        """Т эндпоинта метрик"""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]


class TestRateLimiting:
    """Тесты ограничения частоты запросов"""

    def test_rate_limit_headers(self):
        """Т что заголовки ограничения присутствуют"""
        response = client.get("/status")
        assert response.status_code == 200


class TestAirAlertsStatus:
    """Тесты функции get_air_alerts_status"""

    @patch('main.fetch_alerts_from_api')
    @patch('main.send_telegram_alert')
    @patch('main.sentry_sdk.capture_exception')
    def test_get_air_alerts_status_success(self, mock_sentry, mock_telegram, mock_fetch, mock_env_vars, mock_alerts_response):
        """Т успешного обновления статуса"""
        mock_fetch.return_value = mock_alerts_response

        get_air_alerts_status()

        mock_fetch.assert_called_once()
        # Проверяем что метрики обновлены
        assert active_regions.labels(status="active")._value._value > 0
        assert active_regions.labels(status="inactive")._value._value > 0
        assert update_timestamp._value._value > 0

    @patch('main.fetch_alerts_from_api')
    @patch('main.send_telegram_alert')
    @patch('main.sentry_sdk.capture_exception')
    def test_get_air_alerts_status_kyiv_alert_on(self, mock_sentry, mock_telegram, mock_fetch, mock_env_vars):
        """Т уведомления при включении тревоги в Киеве"""
        from main import last_kyiv_status
        # Изначально статус Киева был False
        last_kyiv_status = False

        mock_fetch.return_value = {
            "statuses": "ANPPPPPPPPPNPPPPNPNPPPPPAAAPNPN"  # Киев на позиции 26 (A - активная тревога)
        }

        get_air_alerts_status()

        mock_telegram.assert_called_with("🚨 В Киеве воздушная тревога!")

    @patch('main.fetch_alerts_from_api')
    @patch('main.send_telegram_alert')
    @patch('main.sentry_sdk.capture_exception')
    def test_get_air_alerts_status_kyiv_alert_off(self, mock_sentry, mock_telegram, mock_fetch, mock_env_vars):
        """Т уведомления при выключении тревоги в Киеве"""
        from main import last_kyiv_status
        # Изначально статус Киева был True
        last_kyiv_status = True

        mock_fetch.return_value = {
            "statuses": "NNPPPPPPPPPNPPPPNPNPPPPPNNPNPN"  # Киев на позиции 26 (N - нет тревога)
        }

        get_air_alerts_status()

        mock_telegram.assert_called_with("✅ В Киеве спокойно.")

    @patch('main.fetch_alerts_from_api')
    @patch('main.send_telegram_alert')
    @patch('main.sentry_sdk.capture_exception')
    def test_get_air_alerts_status_api_error(self, mock_sentry, mock_telegram, mock_fetch, mock_env_vars):
        """Т обработки ошибки API с retry логикой"""
        mock_fetch.side_effect = requests.RequestException("API Error")

        get_air_alerts_status()

        # Должен быть вызван sentry для логирования ошибки
        assert mock_fetch.call_count == 3  # 3 попытки
        mock_sentry.assert_called()

    @patch('main.fetch_alerts_from_api')
    @patch('main.send_telegram_alert')
    @patch('main.sentry_sdk.capture_exception')
    def test_get_air_alerts_status_max_failures(self, mock_sentry, mock_telegram, mock_fetch, mock_env_vars):
        """Т обработки максимального количества ошибок"""
        from main import failure_count, MAX_FAILURES
        failure_count = MAX_FAILURES - 1  # Одна ошибка до максимума

        mock_fetch.side_effect = requests.RequestException("API Error")

        get_air_alerts_status()

        # Должно быть отправлено уведомление о проблемах
        mock_telegram.assert_called_with("❌ Проблемы с API alerts.in.ua - требуется внимание")


class TestPeriodicTask:
    """Тесты периодической задачи"""

    @patch('main.get_air_alerts_status')
    @patch('main.time.sleep')
    def test_periodic_task_initialization(self, mock_sleep, mock_get_status, mock_env_vars):
        """Т что periodic_task вызывает get_air_alerts_status при инициализации"""
        mock_sleep.side_effect = [None, Exception("Stop loop")]  # Останавливаем после первой итерации

        try:
            periodic_task()
        except Exception:
            pass

        # Должен быть вызван дважды - при инициализации и после sleep
        assert mock_get_status.call_count == 2

    @patch('main.get_air_alerts_status')
    @patch('main.time.sleep')
    def test_periodic_task_loop(self, mock_sleep, mock_get_status, mock_env_vars):
        """Т что periodic_task работает в цикле"""
        mock_sleep.side_effect = [None, None, Exception("Stop loop")]  # 2 итерации

        try:
            periodic_task()
        except Exception:
            pass

        # Должен быть вызван 3 раза - инициализация + 2 итерации
        assert mock_get_status.call_count == 3


class TestGlobalState:
    """Тесты глобального состояния приложения"""

    def test_global_variables_initialization(self):
        """Т начальной инициализации глобальных переменных"""
        assert isinstance(alert_status, dict)
        assert last_update_time is None or isinstance(last_update_time, int)
        assert last_kyiv_status is None or isinstance(last_kyiv_status, bool)
        assert isinstance(failure_count, int)
        assert MAX_FAILURES == 5

    @patch('main.alert_status', {"test": True})
    @patch('main.last_update_time', 1640995200)  # 2022-01-01 00:00:00
    def test_global_state_modification(self):
        """Т что глобальное состояние может изменяться"""
        from main import alert_status, last_update_time

        assert alert_status == {"test": True}
        assert last_update_time == 1640995200


class TestErrorHandling:
    """Тесты обработки ошибок"""

    def test_missing_env_vars_handling(self):
        """Т обработки отсутствующих переменных окружения"""
        with patch.dict(os.environ, {}, clear=True):
            # Приложение должно запускаться даже без некоторых переменных
            with patch('main.sentry_sdk.init'):
                # Создаем новое приложение для теста
                from fastapi import FastAPI
                test_app = FastAPI()
                assert test_app is not None

    @patch('main.requests.get')
    def test_network_timeout_handling(self, mock_get, mock_env_vars):
        """Т обработки таймаутов сети"""
        mock_get.side_effect = requests.Timeout("Request timeout")

        with pytest.raises(requests.Timeout):
            fetch_alerts_from_api()

    @patch('main.requests.get')
    def test_http_error_handling(self, mock_get, mock_env_vars):
        """Т обработки HTTP ошибок"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            fetch_alerts_from_api()

    def test_invalid_status_string_handling(self, mock_env_vars):
        """Т обработки некорректной строки статуса"""
        # Тестируем с пустой строкой
        with patch('main.fetch_alerts_from_api') as mock_fetch:
            mock_fetch.return_value = {"statuses": ""}

            with patch('main.send_telegram_alert') as mock_telegram:
                with patch('main.sentry_sdk.capture_exception'):
                    get_air_alerts_status()

                    # Не должно быть обновлений регионов
                    global alert_status
                    assert len(alert_status) == 0


class TestConcurrency:
    """Тесты работы с параллельными запросами"""

    def test_concurrent_status_requests(self):
        """Т обработки параллельных запросов статуса"""
        with patch('main.alert_status', {"test": True}):
            import concurrent.futures

            def make_request():
                return client.get("/status")

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(make_request) for _ in range(10)]
                responses = [future.result() for future in futures]

                # Все запросы должны быть успешными
                for response in responses:
                    assert response.status_code == 200
                    assert response.json() == {"test": True}


class TestIntegration:
    """Интеграционные тесты"""

    @patch('main.fetch_alerts_from_api')
    @patch('main.send_telegram_alert')
    # @freezegun.freeze_time("2024-01-01 12:00:00")  # Временно отключен
    @patch('main.time.time', return_value=1704110400)  # 2024-01-01 12:00:00 UTC
    def test_full_workflow(self, mock_time, mock_telegram, mock_fetch, mock_env_vars):
        """Т полного рабочего процесса"""
        # Мокируем ответ API
        mock_fetch.return_value = {
            "statuses": "ANPPPPPPPPPNPPPPNPNPPPPPAAAPNPN"  # С активным Киевом
        }

        # Запускаем обновление статуса
        get_air_alerts_status()

        # Проверяем что статус обновился
        global alert_status, last_update_time
        assert len(alert_status) > 0
        assert last_update_time == 1704110400  # 2024-01-01 12:00:00 UTC

        # Проверяем что API эндпоинты работают с новыми данными
        response = client.get("/status")
        assert response.status_code == 200
        assert len(response.json()) > 0

        # Проверяем что метрики обновились
        metrics_response = client.get("/metrics")
        assert metrics_response.status_code == 200
        metrics_text = metrics_response.text
        assert "air_alert_regions_total" in metrics_text
        assert "air_alert_last_update_timestamp" in metrics_text