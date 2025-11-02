import pytest
import sys
import os
from unittest.mock import patch, MagicMock
# import freezegun  # Временно отключен для Python 3.13 совместимости

# Добавляем корневую директорию в path для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture
def mock_env_vars():
    """Фикстура для мокирования переменных окружения"""
    env_vars = {
        "TELEGRAM_TOKEN": "test_token",
        "TELEGRAM_CHAT_ID": "123456789",
        "ALERTS_API_TOKEN": "test_api_token",
        "SENTRY_DSN": ""
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars

@pytest.fixture
def mock_alerts_response():
    """Фикстура для мокирования ответа API alerts.in.ua"""
    return {
        "statuses": "ANAPPPPPPPPNNPPPPNPNPPPPPNPNPNPN"
    }

@pytest.fixture
def sample_regions_data():
    """Фикстура с примерными данными регионов"""
    return {
        "Автономна Республіка Крим": False,
        "Волинська область": True,
        "Вінницька область": False,
        "Дніпропетровська область": True,
        "Донецька область": True,
        "Житомирська область": False,
        "Закарпатська область": False,
        "Запорізька область": True,
        "Івано-Франківська область": False,
        "м. Київ": True,
        "Київська область": False,
        "Кіровоградська область": False,
        "Луганська область": True,
        "Львівська область": False,
        "Миколаївська область": True,
        "Одеська область": False,
        "Полтавська область": False,
        "Рівненська область": True,
        "м. Севастополь": False,
        "Сумська область": False,
        "Тернопільська область": False,
        "Харківська область": True,
        "Херсонська область": True,
        "Хмельницька область": False,
        "Черкаська область": False,
        "Чернівецька область": False,
        "Чернігівська область": False
    }

@pytest.fixture
def frozen_time():
    """Фикстура для заморозки времени"""
    # Временно возвращаем mock вместо freezegun
    from unittest.mock import Mock
    mock_time = Mock()
    mock_time.return_value = 1704110400  # 2024-01-01 12:00:00 UTC
    return mock_time