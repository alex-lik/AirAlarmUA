
# 🇺🇦 Ukraine Air Alert Parser API | EN Air Alert Parser | 🇩🇪 Luftalarm-Parser

---

## 🇺🇦 Опис (Ukrainian)

FastAPI-додаток, що парсить карту з сайту [alerts.in.ua](https://alerts.in.ua) і показує, у яких регіонах України оголошена повітряна тривога.

- Фонове оновлення кожні 10 хвилин
- API `/status` повертає статус по регіонах
- Логи зберігаються в `logs/today.log`
- Підтримка відправки помилок у Sentry
- Готово до запуску через Docker та GitHub Actions

## 🚀 Запуск

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 🌐 API

- `GET /status` — словник: область → True/False
- `GET /sentry-debug` — тестова помилка

---

## EN Description (English)

FastAPI app that parses the SVG map from [alerts.in.ua](https://alerts.in.ua) and reports current air alert status across Ukraine by region.

- Background updates every 10 minutes
- `/status` API returns current alert status by region
- Logging to `logs/today.log`
- Sentry integration for error reporting
- Docker and GitHub Actions ready

## 🚀 Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 🌐 API

- `GET /status` — dictionary: region → True/False
- `GET /sentry-debug` — triggers test error

---

## 🇩🇪 Beschreibung (German)

FastAPI-Anwendung, die die SVG-Karte von [alerts.in.ua](https://alerts.in.ua) ausliest und den Luftalarmstatus je Region in der Ukraine bereitstellt.

- Hintergrund-Updates alle 10 Minuten
- API `/status` gibt Alarmstatus pro Region zurück
- Logging nach `logs/today.log`
- Fehler-Tracking via Sentry
- Bereit für Docker & GitHub Actions

## 🚀 Start

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 🌐 API

- `GET /status` — Dictionary: Region → True/False
- `GET /sentry-debug` — Testfehler erzeugen

---

## 🔐 Environment Variables (усі мови)

- `SENTRY_DSN` — Sentry DSN token

## 📦 Docker

```bash
docker compose up --build -d
```

## ☁️ GitHub Actions

- Автодеплой при push в main
- Deploy to server via `scp + ssh`
- Secrets configured in GitHub settings

## 📜 License

MIT License
