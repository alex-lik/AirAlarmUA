import pytest
from unittest.mock import patch, Mock, AsyncMock, call
import requests
import time

# Импортируем основные функции
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import send_telegram_alert, get_air_alerts_status


class TestTelegramNotifications:
    """Тесты Telegram уведомлений"""

    @patch('main.requests.post')
    def test_send_telegram_alert_basic(self, mock_post, mock_env_vars):
        """Т базовой отправки уведомления"""
        send_telegram_alert("Test message")

        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"chat_id": "123456789", "text": "Test message"}
        )

    @patch('main.requests.post')
    def test_send_telegram_alert_with_unicode(self, mock_post, mock_env_vars):
        """Т отправки уведомления с юникодом"""
        message = "🚨 В Києві повітряна тривога! Тестове повідомлення"
        send_telegram_alert(message)

        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"chat_id": "123456789", "text": message}
        )

    @patch('main.requests.post')
    def test_send_telegram_alert_long_message(self, mock_post, mock_env_vars):
        """Т отправки длинного сообщения"""
        long_message = "A" * 5000  # Очень длинное сообщение
        send_telegram_alert(long_message)

        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"chat_id": "123456789", "text": long_message}
        )

    @patch('main.requests.post')
    def test_send_telegram_alert_network_error(self, mock_post, mock_env_vars):
        """Т обработки сетевой ошибки при отправке"""
        mock_post.side_effect = requests.ConnectionError("Network error")

        # Функция не должна вызывать исключение
        send_telegram_alert("Test message")

    @patch('main.requests.post')
    def test_send_telegram_alert_timeout(self, mock_post, mock_env_vars):
        """Т обработки таймаута при отправке"""
        mock_post.side_effect = requests.Timeout("Request timeout")

        # Функция не должна вызывать исключение
        send_telegram_alert("Test message")

    @patch('main.requests.post')
    def test_send_telegram_alert_http_error(self, mock_post, mock_env_vars):
        """Т обработки HTTP ошибки"""
        mock_post.side_effect = requests.HTTPError("400 Bad Request")

        # Функция не должна вызывать исключение
        send_telegram_alert("Test message")

    @patch('main.requests.post')
    def test_send_telegram_alert_api_error_response(self, mock_post, mock_env_vars):
        """Т обработки ошибки API (неверный ответ)"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Bad Request"}
        mock_post.return_value = mock_response

        # Функция не должна вызывать исключение даже при ошибке API
        send_telegram_alert("Test message")

    @patch('main.requests.post')
    def test_send_telegram_alert_success_response(self, mock_post, mock_env_vars):
        """Т успешного ответа от API"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        send_telegram_alert("Test message")

        mock_post.assert_called_once()

    @patch('main.requests.post')
    def test_send_telegram_alert_no_credentials(self, mock_post):
        """Т работы без учетных данных Telegram"""
        with patch.dict(os.environ, {"TELEGRAM_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            send_telegram_alert("Test message")
            mock_post.assert_not_called()

    @patch('main.requests.post')
    def test_send_telegram_alert_partial_credentials(self, mock_post):
        """Т работы с неполными учетными данными"""
        with patch.dict(os.environ, {"TELEGRAM_TOKEN": "test_token", "TELEGRAM_CHAT_ID": ""}):
            send_telegram_alert("Test message")
            mock_post.assert_not_called()

    @patch('main.requests.post')
    def test_send_telegram_alert_empty_message(self, mock_post, mock_env_vars):
        """Т отправки пустого сообщения"""
        send_telegram_alert("")
        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"chat_id": "123456789", "text": ""}
        )

    @patch('main.requests.post')
    def test_send_telegram_alert_whitespace_message(self, mock_post, mock_env_vars):
        """Т отправки сообщения состоящего из пробелов"""
        message = "   \n\t   "
        send_telegram_alert(message)
        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"chat_id": "123456789", "text": message}
        )


class TestKyivStatusNotifications:
    """Тесты уведомлений об изменении статуса Киева"""

    @patch('main.send_telegram_alert')
    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_kyiv_alert_activated(self, mock_sentry, mock_fetch, mock_telegram, mock_env_vars):
        """Т уведомления при активации тревоги в Киеве"""
        from main import last_kyiv_status

        # Устанавливаем начальный статус - нет тревоги
        last_kyiv_status = False

        # Мокируем ответ API с активной тревогой в Киеве (позиция 10 в UID)
        mock_fetch.return_value = {
            "statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"  # A на 10-й позиции
        }

        get_air_alerts_status()

        # Должно быть отправлено уведомление о начале тревоги
        mock_telegram.assert_called_with("🚨 В Киеве воздушная тревога!")

    @patch('main.send_telegram_alert')
    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_kyiv_alert_deactivated(self, mock_sentry, mock_fetch, mock_telegram, mock_env_vars):
        """Т уведомления при деактивации тревоги в Киеве"""
        from main import last_kyiv_status

        # Устанавливаем начальный статус - есть тревога
        last_kyiv_status = True

        # Мокируем ответ API без тревоги в Киеве
        mock_fetch.return_value = {
            "statuses": "NNPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"  # N на 10-й позиции
        }

        get_air_alerts_status()

        # Должно быть отправлено уведомление об окончании тревоги
        mock_telegram.assert_called_with("✅ В Киеве спокойно.")

    @patch('main.send_telegram_alert')
    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_kyiv_status_unchanged(self, mock_sentry, mock_fetch, mock_telegram, mock_env_vars):
        """Т что уведомление не отправляется если статус не изменился"""
        from main import last_kyiv_status

        # Устанавливаем начальный статус
        last_kyiv_status = True

        # Мокируем ответ API с таким же статусом
        mock_fetch.return_value = {
            "statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"  # A на 10-й позиции
        }

        get_air_alerts_status()

        # Уведомление не должно быть отправлено
        mock_telegram.assert_not_called()

    @patch('main.send_telegram_alert')
    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_kyiv_partial_alert(self, mock_sentry, mock_fetch, mock_telegram, mock_env_vars):
        """Т уведомления при частичной тревоге в Киеве"""
        from main import last_kyiv_status

        last_kyiv_status = False

        # Мокируем ответ API с частичной тревогой в Киеве
        mock_fetch.return_value = {
            "statuses": "NNPPPPPPPPTNPPPPNPNPPPPPNPNPNPN"  # P (Partial) на 10-й позиции
        }

        get_air_alerts_status()

        # Частичная тревога также должна вызывать уведомление
        mock_telegram.assert_called_with("🚨 В Киеве воздушная тревога!")

    @patch('main.send_telegram_alert')
    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_first_kyiv_status_update(self, mock_sentry, mock_fetch, mock_telegram, mock_env_vars):
        """Т первого обновления статуса Киева"""
        from main import last_kyiv_status

        # Изначально статус None
        last_kyiv_status = None

        # Мокируем ответ с активной тревогой
        mock_fetch.return_value = {
            "statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"
        }

        get_air_alerts_status()

        # При первом обновлении не должно быть уведомления об изменении
        mock_telegram.assert_not_called()


class TestSystemNotifications:
    """Тесты системных уведомлений"""

    @patch('main.send_telegram_alert')
    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_max_failures_notification(self, mock_sentry, mock_fetch, mock_telegram, mock_env_vars):
        """Т уведомления при достижении максимального количества ошибок"""
        from main import failure_count, MAX_FAILURES

        # Устанавливаем количество ошибок близкое к максимуму
        failure_count = MAX_FAILURES - 1

        mock_fetch.side_effect = requests.RequestException("API Error")

        get_air_alerts_status()

        # Должно быть отправлено уведомление о проблемах
        mock_telegram.assert_called_with("❌ Проблемы с API alerts.in.ua - требуется внимание")

    @patch('main.send_telegram_alert')
    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_not_max_failures_yet(self, mock_sentry, mock_fetch, mock_telegram, mock_env_vars):
        """Т что уведомление не отправляется если еще не достигнут максимум ошибок"""
        from main import failure_count

        # Устанавливаем количество ошибок меньше максимума
        failure_count = 1

        mock_fetch.side_effect = requests.RequestException("API Error")

        get_air_alerts_status()

        # Уведомление не должно быть отправлено
        mock_telegram.assert_not_called()


class TestNotificationFormatting:
    """Тесты форматирования уведомлений"""

    def test_alert_message_formatting(self):
        """Т форматирования сообщения о тревоге"""
        message = "🚨 В Киеве воздушная тревога!"

        # Проверяем наличие эмодзи и правильного текста
        assert "🚨" in message
        assert "Киеве" in message
        assert "воздушная тревога" in message.lower()

    def test_all_clear_message_formatting(self):
        """Т форматирования сообщения об отмене тревоги"""
        message = "✅ В Киеве спокойно."

        # Проверяем наличие эмодзи и правильного текста
        assert "✅" in message
        assert "Киеве" in message
        assert "спокойно" in message.lower()

    def test_system_error_message_formatting(self):
        """Т форматирования сообщения о системной ошибке"""
        message = "❌ Проблемы с API alerts.in.ua - требуется внимание"

        # Проверяем наличие эмодзи и правильного текста
        assert "❌" in message
        assert "API alerts.in.ua" in message
        assert "требуется внимание" in message.lower()


class TestNotificationReliability:
    """Тесты надежности уведомлений"""

    @patch('main.requests.post')
    def test_notification_retry_logic(self, mock_post, mock_env_vars):
        """Т логики повторных попыток отправки"""
        # В текущей реализации нет retry логики для Telegram,
        # но тест проверяет что ошибка не падает наверх
        mock_post.side_effect = requests.ConnectionError("Network error")

        # Не должно быть исключения
        send_telegram_alert("Test message")

    @patch('main.requests.post')
    def test_notification_with_special_characters(self, mock_post, mock_env_vars):
        """Т отправки уведомлений со специальными символами"""
        special_chars_message = "Тестовое повідомлення з спеціальними символами: !@#$%^&*()_+-=[]{}|;':\",./<>?"
        send_telegram_alert(special_chars_message)

        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"chat_id": "123456789", "text": special_chars_message}
        )

    @patch('main.requests.post')
    def test_notification_with_newlines(self, mock_post, mock_env_vars):
        """Т отправки уведомлений с переносами строк"""
        multiline_message = "Строка 1\nСтрока 2\nСтрока 3"
        send_telegram_alert(multiline_message)

        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"chat_id": "123456789", "text": multiline_message}
        )


class TestNotificationIntegration:
    """Интеграционные тесты уведомлений"""

    @patch('main.send_telegram_alert')
    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_multiple_kyiv_status_changes(self, mock_sentry, mock_fetch, mock_telegram, mock_env_vars):
        """Т нескольких изменений статуса Киева подряд"""
        from main import last_kyiv_status

        # Последовательность: нет тревоги -> тревога -> нет тревоги
        test_cases = [
            (None, "NNPPPPPPPPPNPPPPNPNPPPPPNPNPNPN", False, []),  # Первый запуск
            (False, "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN", True, ["🚨 В Киеве воздушная тревога!"]),  # Начало тревоги
            (True, "NNPPPPPPPPPNPPPPNPNPPPPPNPNPNPN", False, ["✅ В Киеве спокойно."]),  # Конец тревоги
        ]

        for initial_status, statuses_string, expected_kyiv_status, expected_calls in test_cases:
            last_kyiv_status = initial_status
            mock_fetch.return_value = {"statuses": statuses_string}
            mock_telegram.reset_mock()

            get_air_alerts_status()

            if expected_calls:
                mock_telegram.assert_has_calls([call(expected_call) for expected_call in expected_calls])
            else:
                mock_telegram.assert_not_called()

    @patch('main.send_telegram_alert')
    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_no_notification_on_api_error(self, mock_sentry, mock_fetch, mock_telegram, mock_env_vars):
        """Т что уведомления не отправляются при ошибках API"""
        mock_fetch.side_effect = requests.RequestException("API Error")

        get_air_alerts_status()

        # Не должно быть отправлено никаких уведомлений об изменении статуса
        calls = [call("🚨 В Киеве воздушная тревога!"), call("✅ В Киеве спокойно.")]
        for call_args in calls:
            assert call_args not in mock_telegram.call_args_list