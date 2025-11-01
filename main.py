
import os
import time
from threading import Thread
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, Response, HTTPException
from loguru import logger
import sentry_sdk
import requests
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    Thread(target=periodic_task, daemon=True).start()
    yield

app = FastAPI(lifespan=lifespan)
Instrumentator().instrument(app).expose(app)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

alert_status = {}
last_update_time = None
last_kyiv_status = None
failure_count = 0
MAX_FAILURES = 5

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALERTS_API_TOKEN = os.getenv("ALERTS_API_TOKEN")

# Соответствие регионов и их UID из API alerts.in.ua
REGIONS_UID_MAP = {
    1: "Автономна Республіка Крим",
    8: "Волинська область",
    4: "Вінницька область",
    9: "Дніпропетровська область",
    28: "Донецька область",
    10: "Житомирська область",
    11: "Закарпатська область",
    12: "Запорізька область",
    13: "Івано-Франківська область",
    31: "м. Київ",
    14: "Київська область",
    15: "Кіровоградська область",
    16: "Луганська область",
    27: "Львівська область",
    17: "Миколаївська область",
    18: "Одеська область",
    19: "Полтавська область",
    5: "Рівненська область",
    30: "м. Севастополь",
    20: "Сумська область",
    21: "Тернопільська область",
    22: "Харківська область",
    23: "Херсонська область",
    3: "Хмельницька область",
    24: "Черкаська область",
    26: "Чернівецька область",
    25: "Чернігівська область"
}

active_regions = Gauge("air_alert_regions_total",
                       "Количество регионов по статусу", ["status"])
update_timestamp = Gauge("air_alert_last_update_timestamp",
                         "Последнее обновление в формате UNIX-времени")


# Инициализация Sentry только если DSN указан
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn and sentry_dsn.strip():
    sentry_sdk.init(
        dsn=sentry_dsn,
        send_default_pii=True,
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Заменить на домены продакшена
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.add('./logs/today.log', level="ERROR",
           rotation="1 day", retention="10 days")



@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests"})


def get_api_headers():
    """Возвращает заголовки для API запросов"""
    if not ALERTS_API_TOKEN:
        raise ValueError("ALERTS_API_TOKEN не установлен в переменных окружения")
    return {
        "Authorization": f"Bearer {ALERTS_API_TOKEN}",
        "Content-Type": "application/json"
    }


def fetch_alerts_from_api():
    """Получает статусы тревог через API alerts.in.ua"""
    url = "https://api.alerts.in.ua/v1/iot/active_air_raid_alerts.json"

    try:
        response = requests.get(url, headers=get_api_headers(), timeout=15)
        response.raise_for_status()

        # API возвращает строку со статусами, а не JSON
        statuses_string = response.text.strip()

        return {"statuses": statuses_string}
    except requests.RequestException as e:
        logger.error(f"Ошибка API запроса: {e}")
        raise


def send_telegram_alert(message: str):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            requests.post(
                url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})
        except Exception as e:
            logger.error(f"Ошибка при отправке Telegram: {e}")


def get_air_alerts_status():
    global alert_status, last_update_time, last_kyiv_status, failure_count
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Получаем данные через API
            api_data = fetch_alerts_from_api()
            regions = {}

            # Парсим строку со статусами регионов
            if 'statuses' in api_data:
                statuses_string = api_data['statuses']

                # Преобразуем строку в список статусов по позициям
                uid_list = sorted(REGIONS_UID_MAP.keys())

                for i, uid in enumerate(uid_list):
                    if i < len(statuses_string):
                        status_char = statuses_string[i]
                        region_name = REGIONS_UID_MAP[uid]

                        # Преобразуем статус API в формат парсера
                        # "A" -> True (активная тревога), "P" -> True (частичная), "N" -> False (нет тревоги)
                        is_alert = status_char in ['A', 'P']
                        regions[region_name] = is_alert

            if not regions:
                logger.warning(f"Не получено данных о регионах (попытка {retry_count + 1})")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)
                continue

            alert_status = regions
            last_update_time = int(time.time())

            active = sum(1 for v in regions.values() if v)
            inactive = sum(1 for v in regions.values() if not v)
            active_regions.labels(status="active").set(active)
            active_regions.labels(status="inactive").set(inactive)
            update_timestamp.set(last_update_time)

            # Отправляем уведомления об изменении статуса Киева
            kyiv_status = regions.get("м. Київ")
            if kyiv_status != last_kyiv_status:
                last_kyiv_status = kyiv_status
                if kyiv_status is True:
                    send_telegram_alert("🚨 В Киеве воздушная тревога!")
                elif kyiv_status is False:
                    send_telegram_alert("✅ В Киеве спокойно.")

            failure_count = 0  # обнуляем ошибки после успеха
            logger.info(f"Успешно обновлен статус {len(regions)} регионов через API")
            return  # Выходим при успехе

        except Exception as e:
            retry_count += 1
            logger.error(f"Ошибка получения данных через API (попытка {retry_count}/{max_retries}): {e}")
            sentry_sdk.capture_exception(e)

            if retry_count < max_retries:
                time.sleep(5)  # Пауза между попытками

    # Если все попытки неудачны
    failure_count += 1
    logger.error(f"Не удалось обновить статус после {max_retries} попыток")

    if failure_count >= MAX_FAILURES:
        send_telegram_alert(
            "❌ Проблемы с API alerts.in.ua - требуется внимание")
        failure_count = 0


def periodic_task():
    # Инициализация - первый запуск
    get_air_alerts_status()

    while True:
        time.sleep(60)  # Пауза в 1 минуту между запросами к API
        get_air_alerts_status()


@app.get("/status")
@limiter.limit("100/10minutes")
def get_status(request: Request):
    return alert_status


@app.get("/region/{name}")
@limiter.limit("100/10minutes")
def get_region_status(request: Request, name: str):
    found = {region: status for region, status in alert_status.items()
             if name.lower() in region.lower()}
    if not found:
        raise HTTPException(status_code=404, detail="Регион не найден")
    return found


@app.get("/sentry-debug")
def trigger_error():
    1 / 0


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
