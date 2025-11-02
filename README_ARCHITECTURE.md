# Документация по архитектуре AirAlarmUA

## Обзор проекта

AirAlarmUA - это современное FastAPI приложение для мониторинга воздушных тревог в Украине с интеграцией Telegram уведомлений и Prometheus метрик.

## Архитектура проекта

Проект следует принципам чистой архитектуры с разделением на слои:

```
E:\ActiveDev\AirAlarmUA\
├── config/              # Конфигурация и константы
│   ├── settings.py      # Настройки приложения с валидацией
│   ├── regions.py       # Данные о регионах Украины
│   └── __init__.py
├── services/            # Бизнес-логика и внешние сервисы
│   ├── alerts_api.py    # Сервис API alerts.in.ua
│   ├── telegram_service.py  # Сервис Telegram уведомлений
│   ├── task_scheduler.py    # Планировщик задач
│   └── __init__.py
├── models/              # Модели данных (Pydantic)
│   ├── alert.py         # Модели статусов тревог
│   └── __init__.py
├── utils/               # Утилиты и вспомогательные модули
│   ├── metrics.py       # Prometheus метрики
│   ├── logger.py        # Конфигурация логирования
│   └── __init__.py
├── api/                 # FastAPI роутеры
│   ├── alerts.py        # Эндпоинты статусов тревог
│   ├── monitoring.py    # Эндпоинты мониторинга
│   └── __init__.py
├── test/                # Тесты
├── logs/                # Логи
├── main.py              # Главный файл приложения
└── requirements.txt     # Зависимости
```

## Основные компоненты

### 1. Конфигурация (`config/`)

**`settings.py`**
- Централизованная конфигурация приложения
- Валидация переменных окружения
- Типизированные настройки с значениями по умолчанию
- Поддержка development и production режимов

**`regions.py`**
- Соответствие UID регионов из API alerts.in.ua
- Списки регионов и приоритетных городов
- Константы для парсинга статусов

### 2. Сервисы (`services/`)

**`AlertsApiService`**
- Интеграция с API alerts.in.ua
- Retry логика с exponential backoff
- Парсинг статусов регионов
- Обработка ошибок и таймаутов

**`TelegramService`**
- Отправка уведомлений в Telegram
- Форматирование сообщений
- Приоритетные уведомления для важных городов
- Проверка соединения с API

**`TaskScheduler`**
- Асинхронный планировщик задач
- Периодическое обновление данных
- Отслеживание изменений статусов
- Отправка уведомлений об изменениях

### 3. Модели данных (`models/`)

**`alert.py`**
- Pydantic модели для валидации данных
- Модели статусов тревог
- Модели ответов API
- Сериализация/десериализация

### 4. Утилиты (`utils/`)

**`metrics.py`**
- Prometheus метрики
- Сбор статистики производительности
- Метрики HTTP запросов
- Метрики работы системы

**`logger.py`**
- Конфигурация loguru
- Структурированное логирование
- Ротация логов
- Контекстное логирование

### 5. API (`api/`)

**`alerts.py`**
- Эндпоинты получения статусов тревог
- Поиск по регионам
- Статистика
- Health checks

**`monitoring.py`**
- Prometheus метрики
- Health endpoints
- Debug endpoints

## Принципы проектирования

### 1. Dependency Injection
- Сервисы инжектируются через функции-фабрики
- Изоляция зависимостей
- Простота тестирования

### 2. Асинхронность
- Все операции I/O асинхронны
- asyncio для concurrent операций
- Эффективное использование ресурсов

### 3. Обработка ошибок
- Структурированная обработка исключений
- Retry логика
- Graceful degradation

### 4. Мониторинг и логирование
- Структурированные логи
- Prometheus метрики
- Sentry интеграция
- Health checks

### 5. Конфигурация
- Environment variables
- Валидация настроек
- Разделение development/production

## Безопасность

### Rate Limiting
- Ограничение запросов к API
- Защита от DDoS
- Настраиваемые лимиты

### CORS
- Настройка разрешенных доменов
- Защита от CSRF
- Production настройки

### Input Validation
- Pydantic модели
- Валидация данных на входе
- Типизация

## Производительность

### Кеширование
- В памяти статусы тревог
- Оптимизация запросов к API
- Эффективное обновление

### Метрики
- Prometheus интеграция
- Мониторинг производительности
- Оповещения о проблемах

## Тестирование

### Структура тестов
```
test/
├── conftest.py          # Фикстуры pytest
├── test_main.py         # Тесты основного приложения
├── test_api_integration.py  # Тесты API
├── test_notifications.py    # Тесты уведомлений
└── test_metrics.py      # Тесты метрик
```

### Типы тестов
- Unit тесты
- Integration тесты
- API тесты
- Performance тесты

## Развертывание

### Environment Variables
```bash
# Обязательные
ALERTS_API_TOKEN=your_api_token

# Опциональные
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
SENTRY_DSN=your_sentry_dsn

# Настройки
UPDATE_INTERVAL=60
MAX_RETRIES=3
RATE_LIMIT=100/10minutes
CORS_ORIGINS=https://yourdomain.com
LOG_LEVEL=INFO
```

### Docker
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Рекомендации по разработке

### 1. Код
- PEP 8 соответствие
- Type hints
- Docstrings (PEP 257)
- Максимальная длина строки 88 символов

### 2. Тестирование
- Покрытие кода > 80%
- Тесты на critical paths
- Mock внешних зависимостей

### 3. Мониторинг
- Логирование всех ошибок
- Метрики производительности
- Health checks

### 4. Документация
- API документация (FastAPI)
- Кодовая документация
- README и архитектура

## Масштабирование

### Horizontal Scaling
- Stateless архитектура
- Внешнее хранилище состояний
- Load balancing

### Database Integration
- Redis для кеширования
- PostgreSQL для истории
- TimescaleDB для метрик

### Monitoring Stack
- Prometheus + Grafana
- Loki для логов
- AlertManager

## Будущие улучшения

### 1. Функциональность
- WebSocket для real-time обновлений
- Push уведомления
- История тревог
- Аналитика и отчеты

### 2. Инфраструктура
- Kubernetes deployment
- CI/CD pipeline
- Blue-green deployment
- Canary releases

### 3. Безопасность
- OAuth2/JWT
- API keys
- Rate limiting improvements
- Input validation enhancements

## Заключение

Архитектура AirAlarmUA спроектирована с учетом современных практик разработки, обеспечивает надежность, масштабируемость и простоту поддержки. Модульная структура позволяет легко добавлять новый функционал и изменять существующий без нарушений работы системы.