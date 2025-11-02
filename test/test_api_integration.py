import pytest
import requests
from unittest.mock import patch, Mock, MagicMock
import time
import json

# Импортируем основные функции
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import fetch_alerts_from_api, get_api_headers, get_air_alerts_status


class TestAlertsAPI:
    """Тесты API alerts.in.ua"""

    @patch('main.requests.get')
    def test_api_request_headers(self, mock_get, mock_env_vars):
        """Т заголовков запроса к API"""
        mock_response = Mock()
        mock_response.text = "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        fetch_alerts_from_api()

        expected_headers = {
            "Authorization": "Bearer test_api_token",
            "Content-Type": "application/json"
        }

        mock_get.assert_called_once_with(
            "https://api.alerts.in.ua/v1/iot/active_air_raid_alerts.json",
            headers=expected_headers,
            timeout=15
        )

    @patch('main.requests.get')
    def test_api_url_correctness(self, mock_get, mock_env_vars):
        """Т правильности URL API"""
        mock_response = Mock()
        mock_response.text = "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        fetch_alerts_from_api()

        call_args = mock_get.call_args
        assert "api.alerts.in.ua" in call_args[0][0]
        assert "/v1/iot/active_air_raid_alerts.json" in call_args[0][0]
        assert call_args[0][0].startswith("https://")

    @patch('main.requests.get')
    def test_api_timeout_configuration(self, mock_get, mock_env_vars):
        """Т конфигурации таймаута"""
        mock_response = Mock()
        mock_response.text = "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        fetch_alerts_from_api()

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["timeout"] == 15

    @patch('main.requests.get')
    def test_api_response_parsing(self, mock_get, mock_env_vars):
        """Т парсинга ответа API"""
        test_statuses = "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"
        mock_response = Mock()
        mock_response.text = test_statuses
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_alerts_from_api()

        assert result == {"statuses": test_statuses}
        assert "statuses" in result

    @patch('main.requests.get')
    def test_api_empty_response(self, mock_get, mock_env_vars):
        """Т обработки пустого ответа API"""
        mock_response = Mock()
        mock_response.text = ""
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_alerts_from_api()

        assert result == {"statuses": ""}

    @patch('main.requests.get')
    def test_api_whitespace_response(self, mock_get, mock_env_vars):
        """Т ответа API состоящего из пробелов"""
        mock_response = Mock()
        mock_response.text = "   \n\t  "
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_alerts_from_api()

        assert result == {"statuses": ""}  # strip() удаляет пробелы

    @patch('main.requests.get')
    def test_api_invalid_response_format(self, mock_get, mock_env_vars):
        """Т ответа API в неверном формате"""
        mock_response = Mock()
        mock_response.text = None
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_alerts_from_api()

        assert result == {"statuses": ""}  # None превращается в пустую строку


class TestAPIErrorHandling:
    """Тесты обработки ошибок API"""

    @patch('main.requests.get')
    def test_connection_error(self, mock_get, mock_env_vars):
        """Т ошибки подключения"""
        mock_get.side_effect = requests.ConnectionError("Connection failed")

        with pytest.raises(requests.ConnectionError):
            fetch_alerts_from_api()

    @patch('main.requests.get')
    def test_timeout_error(self, mock_get, mock_env_vars):
        """Т таймаута"""
        mock_get.side_effect = requests.Timeout("Request timeout")

        with pytest.raises(requests.Timeout):
            fetch_alerts_from_api()

    @patch('main.requests.get')
    def test_http_error_404(self, mock_get, mock_env_vars):
        """Т HTTP 404 ошибки"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            fetch_alerts_from_api()

    @patch('main.requests.get')
    def test_http_error_500(self, mock_get, mock_env_vars):
        """Т HTTP 500 ошибки"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            fetch_alerts_from_api()

    @patch('main.requests.get')
    def test_http_error_403(self, mock_get, mock_env_vars):
        """Т HTTP 403 ошибки (проблемы с авторизацией)"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            fetch_alerts_from_api()

    @patch('main.requests.get')
    def test_json_decode_error_simulation(self, mock_get, mock_env_vars):
        """Т ошибки декодирования JSON (если API вернет JSON вместо строки)"""
        mock_response = Mock()
        mock_response.text = '{"invalid": json}'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Функция должна работать с любым текстом
        result = fetch_alerts_from_api()
        assert result == {"statuses": '{"invalid": json}'}


class TestAPITokenHandling:
    """Тесты обработки токена API"""

    @patch('main.requests.get')
    def test_valid_token(self, mock_get, mock_env_vars):
        """Т работы с валидным токеном"""
        mock_response = Mock()
        mock_response.text = "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_alerts_from_api()
        assert result == {"statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"}

    def test_missing_token(self):
        """Т отсутствия токена"""
        with patch.dict(os.environ, {"ALERTS_API_TOKEN": ""}):
            with pytest.raises(ValueError, match="ALERTS_API_TOKEN не установлен"):
                get_api_headers()

    def test_none_token(self):
        """Т токена равного None"""
        with patch.dict(os.environ, {"ALERTS_API_TOKEN": ""}):
            with pytest.raises(ValueError):
                get_api_headers()

    @patch('main.requests.get')
    def test_invalid_token_response(self, mock_get, mock_env_vars):
        """Т ответа API при невалидном токене"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            fetch_alerts_from_api()


class TestAPIResponseValidation:
    """Тесты валидации ответов API"""

    @patch('main.requests.get')
    @pytest.mark.parametrize("statuses_string", [
        "A" * 27,  # Все активные
        "N" * 27,  # Все неактивные
        "P" * 27,  # Все частичные
        "ANPN" * 6 + "ANP",  # Смешанные
        "",  # Пустая строка
        "X" * 27,  # Невалидные символы
        "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPNEXTRA",  # Слишком длинная строка
    ])
    def test_various_status_strings(self, mock_get, mock_env_vars, statuses_string):
        """Т различных строк статусов"""
        mock_response = Mock()
        mock_response.text = statuses_string
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_alerts_from_api()
        assert result == {"statuses": statuses_string}

    @patch('main.requests.get')
    def test_unicode_handling(self, mock_get, mock_env_vars):
        """Т обработки Unicode в ответе"""
        unicode_text = "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPNßéçαβγ"
        mock_response = Mock()
        mock_response.text = unicode_text
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_alerts_from_api()
        assert result == {"statuses": unicode_text}


class TestAPIRetryLogic:
    """Тесты логики повторных попыток"""

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_retry_on_error(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т повторных попыток при ошибках"""
        from main import failure_count

        # Первые 2 попытки - ошибка, третья - успех
        mock_fetch.side_effect = [
            requests.ConnectionError("Error 1"),
            requests.ConnectionError("Error 2"),
            {"statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"}
        ]

        # Сбрасываем счетчик ошибок
        failure_count = 0

        get_air_alerts_status()

        # Должно быть 3 попытки
        assert mock_fetch.call_count == 3
        # Sentry должен быть вызван для каждой ошибки
        assert mock_sentry.call_count == 2

    @patch('main.fetch_alerts_from_api')
    @patch('main.send_telegram_alert')
    @patch('main.sentry_sdk.capture_exception')
    def test_max_retries_exceeded(self, mock_sentry, mock_telegram, mock_fetch, mock_env_vars):
        """Т превышения максимального количества попыток"""
        from main import failure_count, MAX_FAILURES

        mock_fetch.side_effect = requests.ConnectionError("Persistent error")
        failure_count = 0

        get_air_alerts_status()

        # Должно быть ровно 3 попытки
        assert mock_fetch.call_count == 3
        # Sentry должен быть вызван 3 раза
        assert mock_sentry.call_count == 3

    @patch('main.fetch_alerts_from_api')
    def test_retry_timing(self, mock_fetch, mock_env_vars):
        """Т таймингов между попытками"""
        import time

        mock_fetch.side_effect = [
            requests.ConnectionError("Error 1"),
            requests.ConnectionError("Error 2"),
            {"statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"}
        ]

        start_time = time.time()
        get_air_alerts_status()
        end_time = time.time()

        # Должна быть пауза между попытками (2 секунды)
        assert (end_time - start_time) >= 4  # Минимум 2 паузы по 2 секунды


class TestAPIIntegration:
    """Интеграционные тесты API"""

    @patch('main.fetch_alerts_from_api')
    def test_full_api_workflow(self, mock_fetch, mock_env_vars):
        """Т полного рабочего процесса с API"""
        mock_fetch.return_value = {"statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"}

        get_air_alerts_status()

        # Проверяем что функция была вызвана
        mock_fetch.assert_called_once()

        # Проверяем что глобальное состояние обновилось
        from main import alert_status, last_update_time
        assert len(alert_status) > 0
        assert last_update_time is not None

    @patch('main.fetch_alerts_from_api')
    def test_empty_api_response_handling(self, mock_fetch, mock_env_vars):
        """Т обработки пустого ответа от API"""
        mock_fetch.return_value = {"statuses": ""}

        get_air_alerts_status()

        # Функция делает 3 попытки при пустом ответе
        assert mock_fetch.call_count == 3

    @patch('main.fetch_alerts_from_api')
    def test_api_response_without_statuses(self, mock_fetch, mock_env_vars):
        """Т ответа API без ключа statuses"""
        mock_fetch.return_value = {"other_key": "value"}

        get_air_alerts_status()

        # Функция делает 3 попытки при отсутствии данных
        assert mock_fetch.call_count == 3


class TestAPIPerformance:
    """Тесты производительности API"""

    @patch('main.requests.get')
    def test_api_response_time(self, mock_get, mock_env_vars):
        """Т времени ответа API"""
        import time

        mock_response = Mock()
        mock_response.text = "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        start_time = time.time()
        result = fetch_alerts_from_api()
        end_time = time.time()

        assert result == {"statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"}
        # Время выполнения должно быть минимальным (без реальных сетевых запросов)
        assert (end_time - start_time) < 0.1

    @patch('main.requests.get')
    def test_concurrent_api_calls(self, mock_get, mock_env_vars):
        """Т параллельных вызовов API"""
        import threading
        import queue

        mock_response = Mock()
        mock_response.text = "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        results = queue.Queue()

        def make_api_call():
            try:
                result = fetch_alerts_from_api()
                results.put(result)
            except Exception as e:
                results.put(e)

        # Создаем несколько потоков
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_api_call)
            threads.append(thread)
            thread.start()

        # Ждем завершения
        for thread in threads:
            thread.join()

        # Проверяем результаты
        success_count = 0
        while not results.empty():
            result = results.get()
            if isinstance(result, dict) and "statuses" in result:
                success_count += 1

        assert success_count == 5
        assert mock_get.call_count == 5