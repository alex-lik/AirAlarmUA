#!/usr/bin/env python3
"""Тестовый скрипт для проверки API эндпоинтов."""

import asyncio
import requests
import json
from datetime import datetime

API_BASE_URL = "http://194.61.53.18:8000"

def test_api_endpoints():
    """Тестирование API эндпоинтов."""
    print("=== Тестирование API эндпоинтов AirAlarmUA ===")
    print(f"Базовый URL: {API_BASE_URL}")
    print()

    # Тест 1: /status
    print("1. Тест эндпоинта /status")
    try:
        response = requests.get(f"{API_BASE_URL}/status", timeout=10)
        print(f"   Статус код: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Ответ: {json.dumps(data, indent=2, ensure_ascii=False)[:200]}...")
            print(f"   Ключи в ответе: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        else:
            print(f"   Ошибка: {response.text}")
    except Exception as e:
        print(f"   Исключение: {e}")
    print()

    # Тест 2: /health
    print("2. Тест эндпоинта /health")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        print(f"   Статус код: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Ответ: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"   Ошибка: {response.text}")
    except Exception as e:
        print(f"   Исключение: {e}")
    print()

    # Тест 3: /api/v1/status (проверка что не сломали старый эндпоинт)
    print("3. Тест эндпоинта /api/v1/status (для сравнения)")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/status", timeout=10)
        print(f"   Статус код: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Ответ содержит мета-информацию: {'_meta' in str(data)}")
            print(f"   Ключи в ответе: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        else:
            print(f"   Ошибка: {response.text}")
    except Exception as e:
        print(f"   Исключение: {e}")
    print()

    # Тест 4: /api/v1/health (проверка что не сломали старый эндпоинт)
    print("4. Тест эндпоинта /api/v1/health (для сравнения)")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/health", timeout=10)
        print(f"   Статус код: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Ответ: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"   Ошибка: {response.text}")
    except Exception as e:
        print(f"   Исключение: {e}")
    print()

def test_region_specific():
    """Тестирование региональных запросов."""
    print("=== Тестирование региональных запросов ===")

    # Тест с Черниговской областью
    region = "Чернігівська область"
    print(f"5. Тест эндпоинта /region/{region}")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/region/{region}", timeout=10)
        print(f"   Статус код: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Ответ: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"   Ошибка: {response.text}")
    except Exception as e:
        print(f"   Исключение: {e}")
    print()

if __name__ == "__main__":
    test_api_endpoints()
    test_region_specific()
    print("=== Тестирование завершено ===")