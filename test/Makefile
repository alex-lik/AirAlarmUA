# Makefile для управления тестами AirAlarmUA

.PHONY: help install test test-unit test-integration test-api test-notifications test-metrics test-edge test-fast test-coverage test-style clean docker-test docker-build test-all

# Переменные
PYTHON := python3
PIP := pip3
PYTEST := pytest
DOCKER := docker
TEST_DIR := .

# Цель по умолчанию
help:
	@echo "Доступные команды:"
	@echo "  install         - Установить зависимости для тестов"
	@echo "  test            - Запустить все тесты"
	@echo "  test-unit       - Запустить только unit тесты"
	@echo "  test-integration- Запустить только интеграционные тесты"
	@echo "  test-api        - Запустить только API тесты"
	@echo "  test-notifications - Запустить только тесты уведомлений"
	@echo "  test-metrics    - Запустить только тесты метрик"
	@echo "  test-edge       - Запустить только тесты граничных случаев"
	@echo "  test-fast       - Запустить быстрые тесты"
	@echo "  test-coverage   - Запустить тесты с покрытием"
	@echo "  test-style      - Проверить стиль кода"
	@echo "  clean           - Очистить временные файлы"
	@echo "  docker-build    - Собрать Docker образ для тестов"
	@echo "  docker-test     - Запустить тесты в Docker"
	@echo "  test-all        - Полный цикл тестирования"

# Установка зависимостей
install:
	$(PIP) install -r requirements.txt

# Запуск всех тестов
test:
	$(PYTHON) -m $(PYTEST) $(TEST_DIR) -v --tb=short

# Unit тесты
test-unit:
	$(PYTHON) -m $(PYTEST) $(TEST_DIR) -m "unit or not integration" -v

# Интеграционные тесты
test-integration:
	$(PYTHON) -m $(PYTEST) $(TEST_DIR) -m integration -v

# API тесты
test-api:
	$(PYTHON) -m $(PYTEST) test_api_integration.py -v

# Тесты уведомлений
test-notifications:
	$(PYTHON) -m $(PYTEST) test_notifications.py -v

# Тесты метрик
test-metrics:
	$(PYTHON) -m $(PYTEST) test_metrics.py -v

# Тесты граничных случаев
test-edge:
	$(PYTHON) -m $(PYTEST) test_edge_cases.py -v

# Быстрые тесты
test-fast:
	$(PYTHON) -m $(PYTEST) $(TEST_DIR) -m "not slow" -v

# Тесты с покрытием
test-coverage:
	$(PYTHON) -m $(PYTEST) $(TEST_DIR) \
		--cov=../main \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml \
		--cov-fail-under=80 \
		-v

# Проверка стиля кода
test-style:
	@if command -v black >/dev/null 2>&1; then \
		echo "Проверка стиля кода с помощью black..."; \
		black --check ../main.py; \
	else \
		echo "Black не установлен. Установите: pip install black"; \
	fi
	@if command -v flake8 >/dev/null 2>&1; then \
		echo "Проверка с помощью flake8..."; \
		flake8 ../main.py --max-line-length=100; \
	else \
		echo "Flake8 не установлен. Установите: pip install flake8"; \
	fi

# Очистка временных файлов
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -f coverage.xml
	rm -f .coverage

# Сборка Docker образа
docker-build:
	$(DOCKER) build -f Dockerfile.test -t airalarmua-tests ..

# Запуск тестов в Docker
docker-test:
	$(DOCKER) run --rm airalarmua-tests

# Полный цикл тестирования
test-all: clean install test-coverage test-style
	@echo ""
	@echo "=== Полный цикл тестирования завершен ==="
	@echo "Отчет покрытия: htmlcov/index.html"
	@echo ""

# Запуск специфичных тестовых файлов
test-main:
	$(PYTHON) -m $(PYTEST) test_main.py -v

test-fastapi:
	$(PYTHON) -m $(PYTEST) test_fastapi_integration.py -v

test-config:
	$(PYTHON) -m $(PYTEST) test_config.py -v

# Запуск тестов с детальным выводом
test-verbose:
	$(PYTHON) -m $(PYTEST) $(TEST_DIR) -v -s

# Запуск тестов с остановкой на первой ошибке
test-fail-fast:
	$(PYTHON) -m $(PYTEST) $(TEST_DIR) -x -v

# Показать самые медленные тесты
test-slowest:
	$(PYTHON) -m $(PYTEST) $(TEST_DIR) --durations=10

# Запуск только упавших тестов
test-failed:
	$(PYTHON) -m $(PYTEST) $(TEST_DIR) --lf -v

# Параллельный запуск тестов (требует pytest-xdist)
test-parallel:
	@if command -v pytest-xdist >/dev/null 2>&1; then \
		$(PYTHON) -m $(PYTEST) $(TEST_DIR) -n auto -v; \
	else \
		echo "pytest-xdist не установлен. Установите: pip install pytest-xdist"; \
		$(MAKE) test; \
	fi

# Генерация отчета в JUnit формате (для CI)
test-junit:
	$(PYTHON) -m $(PYTEST) $(TEST_DIR) --junitxml=test-results.xml -v

# Запуск с профилированием (требует pytest-profiling)
test-profile:
	@if command -v pytest-profiling >/dev/null 2>&1; then \
		$(PYTHON) -m $(PYTEST) $(TEST_DIR) --profile -v; \
	else \
		echo "pytest-profiling не установлен. Установите: pip install pytest-profiling"; \
		$(MAKE) test; \
	fi

# Запуск с benchmark (требует pytest-benchmark)
test-benchmark:
	@if command -v pytest-benchmark >/dev/null 2>&1; then \
		$(PYTHON) -m $(PYTEST) $(TEST_DIR) --benchmark-only -v; \
	else \
		echo "pytest-benchmark не установлен. Установите: pip install pytest-benchmark"; \
		$(MAKE) test-fast; \
	fi

# Проверка зависимостей на уязвимости
test-security:
	@if command -v safety >/dev/null 2>&1; then \
		safety check; \
	else \
		echo "Safety не установлен. Установите: pip install safety"; \
	fi

# Запуск тестов для CI/CD
test-ci: clean install test-coverage test-junit
	@echo "Тесты для CI/CD завершены"

# Разработка: запуск тестов при изменении файлов
test-watch:
	@if command -v pytest-watch >/dev/null 2>&1; then \
		ptw $(TEST_DIR); \
	else \
		echo "pytest-watch не установлен. Установите: pip install pytest-watch"; \
	fi

# Подсчет количества тестов
count-tests:
	@echo "Всего тестов:"
	@$(PYTHON) -m $(PYTEST) $(TEST_DIR) --collect-only | grep -c "test_"

# Статистика по покрытию
coverage-stats:
	@if [ -f htmlcov/index.html ]; then \
		echo "Отчет покрытия доступен: htmlcov/index.html"; \
	else \
		$(MAKE) test-coverage; \
	fi