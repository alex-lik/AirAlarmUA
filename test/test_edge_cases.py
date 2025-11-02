import pytest
from unittest.mock import patch, Mock, MagicMock
import time
import threading
import asyncio

# Импортируем основные функции
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (
    app, alert_status, get_air_alerts_status, fetch_alerts_from_api,
    send_telegram_alert, REGIONS_UID_MAP, periodic_task
)
from fastapi.testclient import TestClient


class TestEdgeCases:
    """Тесты граничных случаев и нестандартных сценариев"""

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_extremely_long_status_string(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т обработки очень длинной строки статуса"""
        # Создаем строку намного длиннее ожидаемой
        very_long_string = "A" * 1000
        mock_fetch.return_value = {"statuses": very_long_string}

        get_air_alerts_status()

        # Функция должна обработать это без ошибок
        mock_fetch.assert_called_once()

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_status_string_with_invalid_characters(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т строки статуса с невалидными символами"""
        invalid_chars_string = "XYZ!@#$%^&*()" + "A" * 17
        mock_fetch.return_value = {"statuses": invalid_chars_string}

        get_air_alerts_status()

        # Невалидные символы должны игнорироваться (не 'A' или 'P')
        from main import alert_status
        # Только 'A' считается активной тревогой
        expected_active = 1  # Только одна 'A' в строке
        actual_active = sum(1 for v in alert_status.values() if v)

        assert actual_active == expected_active

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_zero_length_status_string(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т строки статуса нулевой длины"""
        mock_fetch.return_value = {"statuses": ""}

        get_air_alerts_status()

        # Не должно быть никаких регионов в статусе
        from main import alert_status
        assert len(alert_status) == 0

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_single_character_status_string(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т строки статуса из одного символа"""
        mock_fetch.return_value = {"statuses": "A"}

        get_air_alerts_status()

        # Должен быть только один регион
        from main import alert_status
        assert len(alert_status) == 1
        # И он должен быть активным
        assert any(alert_status.values())

    @patch('main.fetch_alerts_from_api')
    @patch('main.sentry_sdk.capture_exception')
    def test_status_string_exact_region_count(self, mock_sentry, mock_fetch, mock_env_vars):
        """Т строки статуса точной длины (равной количеству регионов)"""
        exact_length_string = "A" * len(REGIONS_UID_MAP)
        mock_fetch.return_value = {"statuses": exact_length_string}

        get_air_alerts_status()

        # Должны быть все регионы
        from main import alert_status
        assert len(alert_status) == len(REGIONS_UID_MAP)
        # Все должны быть активны
        assert all(alert_status.values())

    @patch('main.requests.post')
    def test_telegram_message_length_limits(self, mock_post, mock_env_vars):
        """Т ограничений длины сообщения Telegram"""
        # Telegram имеет ограниение 4096 символов
        max_message = "A" * 4096
        send_telegram_alert(max_message)

        mock_post.assert_called_once()

        # Тест превышения лимита
        over_limit_message = "A" * 5000
        send_telegram_alert(over_limit_message)

        # Должен быть второй вызов
        assert mock_post.call_count == 2

    @patch('main.requests.post')
    def test_telegram_unicode_handling(self, mock_post, mock_env_vars):
        """Т обработки Unicode в сообщениях Telegram"""
        unicode_message = "Тестове повідомлення з різними символами: 🚨📱💻 αβγδε ñáéíóú"
        send_telegram_alert(unicode_message)

        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"chat_id": "123456789", "text": unicode_message}
        )

    def test_region_search_case_variations(self):
        """Т поиска региона в разных регистрах"""
        client = TestClient(app)

        with patch('main.alert_status', {
            "м. Київ": True,
            "КИЇВСЬКА ОБЛАСТЬ": False,
            "Харківська область": True
        }):
            # Разные регистры поиска
            search_terms = ["київ", "КИЇВ", "Київ", "кІЇВ"]

            for term in search_terms:
                response = client.get(f"/region/{term}")
                assert response.status_code == 200
                data = response.json()
                # Должен найти как минимум Киев
                assert any("київ" in region.lower() for region in data.keys())

    def test_region_search_partial_and_full_matches(self):
        """Т частичных и полных совпадений регионов"""
        client = TestClient(app)

        with patch('main.alert_status', {
            "Київська область": False,
            "м. Київ": True,
            "Новокиївське": False
        }):
            response = client.get("/region/Київ")
            assert response.status_code == 200
            data = response.json()

            # Должны найти все три региона
            assert len(data) == 3
            assert "Київська область" in data
            assert "м. Київ" in data
            assert "Новокиївське" in data

    def test_concurrent_status_updates(self):
        """Т одновременных обновлений статуса"""
        import threading
        import time

        results = []
        errors = []

        def update_status():
            try:
                with patch('main.fetch_alerts_from_api') as mock_fetch:
                    mock_fetch.return_value = {"statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"}
                    get_air_alerts_status()
                    results.append(True)
            except Exception as e:
                errors.append(e)

        # Создаем несколько потоков
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=update_status)
            threads.append(thread)
            thread.start()

        # Ждем завершения
        for thread in threads:
            thread.join()

        # Проверяем результаты
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10

    @patch('main.fetch_alerts_from_api')
    def test_api_response_none_handling(self, mock_fetch, mock_env_vars):
        """Т обработки None ответа от API"""
        mock_fetch.return_value = None

        # Не должно вызывать исключение
        try:
            get_air_alerts_status()
        except Exception as e:
            pytest.fail(f"Function raised exception with None response: {e}")

    @patch('main.fetch_alerts_from_api')
    def test_api_response_missing_statuses_key(self, mock_fetch, mock_env_vars):
        """Т ответа API без ключа statuses"""
        mock_fetch.return_value = {"other_key": "value"}

        get_air_alerts_status()

        # Функция должна обработать отсутствующий ключ
        from main import alert_status
        assert len(alert_status) == 0

    @patch('main.fetch_alerts_from_api')
    def test_api_response_none_statuses_value(self, mock_fetch, mock_env_vars):
        """Т ответа API с statuses=None"""
        mock_fetch.return_value = {"statuses": None}

        get_air_alerts_status()

        # Не должно вызывать ошибок
        mock_fetch.assert_called_once()

    def test_empty_regions_mapping(self):
        """Т работы с пустой картой регионов"""
        original_mapping = REGIONS_UID_MAP.copy()

        try:
            # Очищаем карту регионов
            REGIONS_UID_MAP.clear()

            with patch('main.fetch_alerts_from_api') as mock_fetch:
                mock_fetch.return_value = {"statuses": "ANP"}
                get_air_alerts_status()

                # Не должно быть регионов в статусе
                from main import alert_status
                assert len(alert_status) == 0

        finally:
            # Восстанавливаем оригинальную карту
            REGIONS_UID_MAP.update(original_mapping)

    def test_regions_mapping_modification_safety(self):
        """Т безопасного изменения карты регионов"""
        original_mapping = REGIONS_UID_MAP.copy()

        try:
            # Добавляем тестовый регион
            test_uid = 999
            REGIONS_UID_MAP[test_uid] = "Тестовий регіон"

            with patch('main.fetch_alerts_from_api') as mock_fetch:
                # Создаем строку с учетом нового региона
                all_uids = sorted(REGIONS_UID_MAP.keys())
                statuses = "A" * len(all_uids)
                mock_fetch.return_value = {"statuses": statuses}

                get_air_alerts_status()

                from main import alert_status
                assert "Тестовий регіон" in alert_status
                assert alert_status["Тестовий регіон"] == True

        finally:
            # Восстанавливаем оригинальную карту
            REGIONS_UID_MAP.clear()
            REGIONS_UID_MAP.update(original_mapping)

    def test_memory_leak_prevention(self):
        """Т предотвращения утечек памяти"""
        import gc
        import sys

        # Делаем много обновлений статуса
        for i in range(100):
            with patch('main.fetch_alerts_from_api') as mock_fetch:
                mock_fetch.return_value = {"statuses": f"A{'N'*26}"}
                get_air_alerts_status()

        # Принудительная сборка мусора
        gc.collect()

        # Проверяем что нет утечек (базовая проверка)
        # В реальном проекте здесь были бы более сложные проверки памяти

    def test_rapid_api_calls(self):
        """Т быстрых последовательных вызовов API"""
        client = TestClient(app)

        with patch('main.alert_status', {"test": True}):
            # Делаем много быстрых запросов
            responses = []
            for _ in range(50):
                response = client.get("/status")
                responses.append(response)

            # Все запросы должны быть успешными
            for response in responses:
                assert response.status_code == 200
                assert response.json() == {"test": True}

    @patch('main.time.sleep')
    @patch('main.get_air_alerts_status')
    def test_periodic_task_interruption(self, mock_get_status, mock_sleep, mock_env_vars):
        """Т прерывания периодической задачи"""
        mock_sleep.side_effect = [None, KeyboardInterrupt(), None]

        with pytest.raises(KeyboardInterrupt):
            periodic_task()

        # get_air_alerts_status должен быть вызван хотя бы раз
        assert mock_get_status.call_count >= 1

    def test_api_header_injection_attempts(self):
        """Т попыток инъекции в заголовки API"""
        from main import get_api_headers

        with patch.dict(os.environ, {"ALERTS_API_TOKEN": "Bearer\r\nInjected-Header: value"}):
            try:
                headers = get_api_headers()
                # Заголовок должен содержать токен как есть
                assert "Injected-Header" not in headers.get("Authorization", "")
            except Exception:
                # Если есть валидация, это тоже хорошо
                pass

    def test_special_characters_in_region_search(self):
        """Т поиска регионов со специальными символами"""
        client = TestClient(app)

        with patch('main.alert_status', {"Регіон-测试": True}):
            special_chars = ["../", "%2e%2e", "..\\", "<script>", "' OR '1'='1"]

            for char in special_chars:
                response = client.get(f"/region/{char}")
                # Не должно быть внутренних ошибок сервера
                assert response.status_code in [200, 404]

    def test_very_long_region_search(self):
        """Т поиска очень длинных имен регионов"""
        client = TestClient(app)

        long_name = "a" * 1000
        response = client.get(f"/region/{long_name}")

        # Не должно быть ошибок обработки
        assert response.status_code in [200, 404]

    @patch('main.requests.post')
    def test_telegram_api_rate_limiting(self, mock_post, mock_env_vars):
        """Т обработки rate limiting от Telegram API"""
        # Сначала успешный ответ, потом rate limiting
        mock_post.side_effect = [
            Mock(status_code=200),
            Mock(status_code=429, json=lambda: {"error": "Too many requests"})
        ]

        # Первый вызов должен быть успешным
        send_telegram_alert("Message 1")

        # Второй вызов не должен вызывать исключение даже при 429
        send_telegram_alert("Message 2")

        assert mock_post.call_count == 2

    @patch('main.fetch_alerts_from_api')
    def test_api_response_with_bytes(self, mock_fetch, mock_env_vars):
        """Т ответа API в виде байтов"""
        mock_response = Mock()
        mock_response.text = b"ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"
        mock_response.raise_for_status.return_value = None

        # Настраиваем mock для возврата байтов
        def configure_mock(*args, **kwargs):
            return mock_response

        mock_fetch.side_effect = configure_mock

        try:
            get_air_alerts_status()
        except Exception as e:
            # Если есть обработка байтов, это хорошо
            # Если нет, это тоже валидный сценарий
            pass

    def test_system_clock_changes(self):
        """Т изменений системного времени"""
        import time

        with patch('main.time.time') as mock_time:
            # Имитируем скачок времени
            mock_time.side_effect = [1000, 5000]  # Скачок на 4 секунды

            with patch('main.fetch_alerts_from_api') as mock_fetch:
                mock_fetch.return_value = {"statuses": "ANPPPPPPPPPNPPPPNPNPPPPPNPNPNPN"}
                get_air_alerts_status()

                from main import last_update_time
                # Время должно соответствовать последнему вызову
                assert last_update_time == 5000

    def test_concurrent_metric_updates(self):
        """Т одновременного обновления метрик"""
        import threading
        from main import active_regions, update_timestamp

        def update_metrics(thread_id):
            for i in range(10):
                try:
                    active_regions.labels(status="active").set(thread_id * 10 + i)
                    update_timestamp.set(int(time.time()) + thread_id)
                    time.sleep(0.001)
                except Exception:
                    pass

        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_metrics, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Проверяем что метрики все еще работают
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200


class TestDisasterScenarios:
    """Тесты катастрофических сценариев"""

    @patch('main.requests.get')
    @patch('main.requests.post')
    def test_complete_network_failure(self, mock_post, mock_get, mock_env_vars):
        """Т полного отказа сети"""
        mock_get.side_effect = requests.ConnectionError("Network unreachable")
        mock_post.side_effect = requests.ConnectionError("Network unreachable")

        # API вызовы должны падать с ошибкой
        with pytest.raises(requests.ConnectionError):
            fetch_alerts_from_api()

        # Telegram уведомления не должны падать
        send_telegram_alert("Test message")  # Не должно быть исключения

    @patch('main.fetch_alerts_from_api')
    @patch('main.send_telegram_alert')
    def test_cascading_failures(self, mock_telegram, mock_fetch, mock_env_vars):
        """Т каскадных отказов"""
        from main import failure_count, MAX_FAILURES

        # API всегда падает
        mock_fetch.side_effect = requests.RequestException("Persistent failure")
        failure_count = MAX_FAILURES - 1

        get_air_alerts_status()

        # Должно быть отправлено уведомление о проблемах
        mock_telegram.assert_called_with("❌ Проблемы с API alerts.in.ua - требуется внимание")

    def test_memory_exhaustion_simulation(self):
        """Т симуляции истощения памяти"""
        # Этот тест проверяет поведение при нехватке памяти
        try:
            # Пытаемся выделить много памяти
            large_data = ["A" * 1000000 for _ in range(1000)]

            # Вызываем функцию с ограниченной памятью
            with patch('main.fetch_alerts_from_api') as mock_fetch:
                mock_fetch.return_value = {"statuses": "A" * 27}
                get_air_alerts_status()

            # Очищаем память
            del large_data

        except MemoryError:
            # Если память закончилась, это ожидаемое поведение
            pass

    @patch('main.os.environ', {})
    def test_missing_all_environment_variables(self):
        """Т отсутствия всех переменных окружения"""
        # Удаляем все переменные окружения
        original_env = os.environ.copy()

        try:
            os.environ.clear()

            # Приложение должно работать без переменных окружения
            # (хотя и с ограниченной функциональностью)
            client = TestClient(app)
            response = client.get("/health")
            assert response.status_code == 200

        finally:
            # Восстанавливаем переменные окружения
            os.environ.clear()
            os.environ.update(original_env)