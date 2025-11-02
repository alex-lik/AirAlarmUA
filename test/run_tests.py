#!/usr/bin/env python3
"""
Скрипт для запуска тестов с различными опциями
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, cwd=None):
    """Выполняет команду и возвращает результат"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode == 0


def run_unit_tests():
    """Запуск только unit тестов"""
    print("\n=== Running Unit Tests ===")
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", "unit or not integration",
        "test/test_main.py",
        "test/test_fastapi_integration.py",
        "test/test_notifications.py",
        "test/test_api_integration.py",
        "test/test_metrics.py",
        "test/test_edge_cases.py",
        "-v"
    ]
    return run_command(cmd)


def run_integration_tests():
    """Запуск только интеграционных тестов"""
    print("\n=== Running Integration Tests ===")
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", "integration",
        "-v"
    ]
    return run_command(cmd)


def run_api_tests():
    """Запуск только API тестов"""
    print("\n=== Running API Tests ===")
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", "api",
        "test/test_api_integration.py",
        "-v"
    ]
    return run_command(cmd)


def run_notification_tests():
    """Запуск только тестов уведомлений"""
    print("\n=== Running Notification Tests ===")
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", "notifications",
        "test/test_notifications.py",
        "-v"
    ]
    return run_command(cmd)


def run_metrics_tests():
    """Запуск только тестов метрик"""
    print("\n=== Running Metrics Tests ===")
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", "metrics",
        "test/test_metrics.py",
        "-v"
    ]
    return run_command(cmd)


def run_edge_cases_tests():
    """Запуск только тестов граничных случаев"""
    print("\n=== Running Edge Cases Tests ===")
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", "edge_cases",
        "test/test_edge_cases.py",
        "-v"
    ]
    return run_command(cmd)


def run_all_tests():
    """Запуск всех тестов"""
    print("\n=== Running All Tests ===")
    cmd = [
        sys.executable, "-m", "pytest",
        ".",
        "-v",
        "--cov=../main",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov"
    ]
    return run_command(cmd)


def run_fast_tests():
    """Запуск быстрых тестов (без медленных)"""
    print("\n=== Running Fast Tests Only ===")
    cmd = [
        sys.executable, "-m", "pytest",
        ".",
        "-m", "not slow",
        "-v"
    ]
    return run_command(cmd)


def run_coverage_report():
    """Генерация подробного отчета покрытия"""
    print("\n=== Generating Coverage Report ===")
    cmd = [
        sys.executable, "-m", "pytest",
        ".",
        "--cov=../main",
        "--cov-report=html:htmlcov",
        "--cov-report=xml:coverage.xml",
        "--cov-report=term",
        "--cov-fail-under=70"
    ]
    return run_command(cmd)


def install_dependencies():
    """Установка зависимостей для тестов"""
    print("\n=== Installing Test Dependencies ===")
    cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    return run_command(cmd)


def check_code_style():
    """Проверка стиля кода"""
    print("\n=== Checking Code Style ===")

    # Проверка с помощью black (если доступен)
    try:
        cmd = [sys.executable, "-m", "black", "--check", "../main.py"]
        if not run_command(cmd):
            print("Code style issues found. Run 'black ../main.py' to fix.")
            return False
    except ImportError:
        print("Black not installed. Skipping style check.")

    # Проверка с помощью flake8 (если доступен)
    try:
        cmd = [sys.executable, "-m", "flake8", "../main.py", "--max-line-length=100"]
        if not run_command(cmd):
            print("Flake8 issues found.")
            return False
    except ImportError:
        print("Flake8 not installed. Skipping linting.")

    return True


def main():
    parser = argparse.ArgumentParser(description="Test runner for AirAlarmUA")

    parser.add_argument(
        "command",
        choices=[
            "all", "unit", "integration", "api", "notifications",
            "metrics", "edge", "fast", "coverage", "install", "style"
        ],
        help="Тип тестов для запуска"
    )

    parser.add_argument(
        "--no-install",
        action="store_true",
        help="Не устанавливать зависимости автоматически"
    )

    args = parser.parse_args()

    # Переходим в директорию с тестами
    test_dir = Path(__file__).parent
    os.chdir(test_dir)

    success = True

    # Устанавливаем зависимости если нужно
    if not args.no_install:
        if not install_dependencies():
            print("Failed to install dependencies")
            sys.exit(1)

    # Запускаем нужные тесты
    if args.command == "all":
        success = run_all_tests()
    elif args.command == "unit":
        success = run_unit_tests()
    elif args.command == "integration":
        success = run_integration_tests()
    elif args.command == "api":
        success = run_api_tests()
    elif args.command == "notifications":
        success = run_notification_tests()
    elif args.command == "metrics":
        success = run_metrics_tests()
    elif args.command == "edge":
        success = run_edge_cases_tests()
    elif args.command == "fast":
        success = run_fast_tests()
    elif args.command == "coverage":
        success = run_coverage_report()
    elif args.command == "install":
        success = install_dependencies()
    elif args.command == "style":
        success = check_code_style()

    # Выводим результаты
    if success:
        print(f"\n[SUCCESS] {args.command.upper()} tests passed successfully!")
        if args.command in ["all", "coverage"]:
            print("\n[INFO] Coverage report generated in htmlcov/index.html")
    else:
        print(f"\n[FAILED] {args.command.upper()} tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()