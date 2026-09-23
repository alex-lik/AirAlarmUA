# AirAlarmUA

FastAPI service that polls [alerts.in.ua](https://alerts.in.ua) and exposes the current
air-raid alert status per Ukrainian region, with Telegram notifications,
Prometheus metrics, and Docker-ready deployment.

## Features

- Polling of `alerts.in.ua` API with retry + exponential backoff
- Region status API (`/api/v1/status`, `/api/v1/region/{name}`, `/api/v1/stats`)
- Telegram notifications on status changes (priority alerts for Kyiv)
- Prometheus metrics (`/metrics`), health checks, rate limiting, CORS
- Sentry error tracking (optional)
- Background scheduler tracking changes and failures
- Docker + Docker Compose, GitHub Actions deploy, Nginx example

## Stack

Python 3.13, FastAPI, Uvicorn, Pydantic, Loguru, SlowAPI,
`prometheus_client`, `prometheus-fastapi-instrumentator`, Requests, Sentry SDK.

## Quickstart

```bash
cp .env.example .env
# set ALERTS_API_TOKEN in .env

pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open:

- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- Status: `http://localhost:8000/api/v1/status`

## Configuration

See [.env.example](.env.example). Main variables:

| Variable | Default | Description |
|---|---|---|
| `ALERTS_API_TOKEN` | `development_token` | Token for `alerts.in.ua` API |
| `ALERTS_API_URL` | `.../active_air_raid_alerts.json` | Status feed URL |
| `UPDATE_INTERVAL` | `60` | Poll interval, seconds |
| `REQUEST_TIMEOUT` | `15` | Upstream timeout, seconds |
| `MAX_RETRIES` / `MAX_FAILURES` | `3` / `5` | Retry / failure thresholds |
| `RATE_LIMIT` | `100/10minutes` | SlowAPI limit string |
| `CORS_ORIGINS` | `*` | Comma-separated origins |
| `PORT` / `LOG_LEVEL` / `LOG_FILE` | `8500` / `INFO` / — | Server / logging |
| `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID` | — | Telegram notifications (optional) |
| `SENTRY_DSN` | — | Sentry tracking (optional) |

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/status` | All regions with metadata |
| `GET` | `/api/v1/region/{name}` | Search regions by name substring |
| `GET` | `/api/v1/stats` | Aggregated alert statistics |
| `GET` | `/api/v1/health` | Service + dependency health |
| `GET` | `/status`, `/health` | Legacy aliases without prefix |
| `GET` | `/health/simple`, `/ping` | Liveness probes |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/info` | App info and feature flags |
| `GET` | `/debug/services` | Scheduler state (dev only) |
| `GET` | `/sentry-debug` | Test Sentry error (dev only) |

Example:

```bash
curl http://localhost:8000/api/v1/stats
```

## Architecture

```text
.
├── main.py            # app factory, lifespan, middleware, exception handlers
├── config/            # settings (env), region UID map
├── services/          # alerts.in.ua client, Telegram, background scheduler
├── api/               # routers: alerts (/api/v1), monitoring, legacy aliases
├── models/            # Pydantic models (RegionStatus, AlertSystemStatus, ...)
├── utils/             # loguru setup, Prometheus collector
├── test/              # pytest suite
├── Dockerfile / docker-compose*.yml
├── deploy.sh
└── nginx/             # reverse-proxy example
```

Flow: `TaskScheduler` polls `AlertsApiService` every `UPDATE_INTERVAL`,
caches `AlertSystemStatus`, diffs it against the previous snapshot, sends
Telegram notifications on changes, updates Prometheus gauges, and exposes
the latest snapshot via FastAPI routers. Failures increment a counter and
trigger a system alert after `MAX_FAILURES`.

## Tests

```bash
pip install -r requirements.txt
pip install -r test/requirements.txt

pytest -v
pytest test/test_app.py -v
pytest test/test_services.py -v
```

See [test/README.md](test/README.md).

## Docker

```bash
docker compose up --build -d
curl -f http://localhost:8000/health
```

Production:

```bash
cp .env.example .env
# fill secrets, then:
docker compose -f docker-compose.prod.yml up --build -d
# or:
./deploy.sh
```

Behind Nginx see [nginx/nginx.md](nginx/nginx.md).

## Deploy

Push to `main` triggers [.github/workflows/deploy.yml](.github/workflows/deploy.yml):
copy via SCP, write `.env` from secrets, `docker compose build/up`.
Pull requests and pushes run tests via [.github/workflows/ci.yml](.github/workflows/ci.yml).

## License

MIT — see [LICENSE](LICENSE).
