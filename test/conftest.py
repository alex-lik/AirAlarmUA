import os
import sys
from unittest.mock import patch

import pytest

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for tests."""
    env_vars = {
        "TELEGRAM_TOKEN": "123456:TEST_TOKEN",
        "TELEGRAM_CHAT_ID": "123456789",
        "ALERTS_API_TOKEN": "test_api_token_12345",
        "SENTRY_DSN": "",
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars
