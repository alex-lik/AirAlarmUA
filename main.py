
import os
import time
from threading import Thread
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, Response, HTTPException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
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

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    send_default_pii=True,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Заменить на домены продакшена
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.add('./logs/today.log', level="ERROR", rotation="1 day", retention="10 days")

Instrumentator().instrument(app).expose(app)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests"})

alert_status = {}
last_update_time = None
driver = None
last_kyiv_status = None
failure_count = 0
MAX_FAILURES = 5

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

active_regions = Gauge("air_alert_regions_total", "Количество регионов по статусу", ["status"])
update_timestamp = Gauge("air_alert_last_update_timestamp", "Последнее обновление в формате UNIX-времени")

def check_label(label: str) -> bool:
    ukr_letters = set("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя")
    return bool(label) and any(l in ukr_letters for l in label)

def setup_browser():
    global driver
    if driver:
        return
    options = Options()
    # options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1024,768")
    service = Service(log_path=os.devnull)
    driver = webdriver.Chrome(options=options, service=service)
    driver.set_page_load_timeout(15)
    driver.get("https://alerts.in.ua") 
    driver.implicitly_wait(10)


def send_telegram_alert(message: str):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})
        except Exception as e:
            logger.error(f"Ошибка при отправке Telegram: {e}")

def get_air_alerts_status():
    global alert_status, last_update_time, driver, last_kyiv_status, failure_count
    try:
        setup_browser()



        regions = {}
        elements = driver.find_elements(By.TAG_NAME, "text")

        for el in elements:
            label = el.text.strip()
            if not check_label(label):
                continue
            class_attr = el.get_attribute("class")
            print(label, class_attr)
            is_alert = "active" in class_attr
            regions[label] = is_alert

        alert_status = regions
        last_update_time = int(time.time())
        # logger.success("Данные тревоги обновлены.")

        active = sum(1 for v in regions.values() if v)
        inactive = sum(1 for v in regions.values() if not v)
        active_regions.labels(status="active").set(active)
        active_regions.labels(status="inactive").set(inactive)
        update_timestamp.set(last_update_time)

        kyiv_status = regions.get("м. Київ")
        if kyiv_status != last_kyiv_status:
            last_kyiv_status = kyiv_status
            if kyiv_status is True:
                send_telegram_alert("🚨 В Киеве воздушная тревога!")
            elif kyiv_status is False:
                send_telegram_alert("✅ В Киеве спокойно.")

        failure_count = 0  # обнуляем ошибки после успеха

    except Exception as e:
        failure_count += 1
        logger.error(f"Ошибка при обновлении тревог: {e}")
        sentry_sdk.capture_exception(e)

        if failure_count >= MAX_FAILURES:
            send_telegram_alert("❌ 5 подряд ошибок при обновлении alerts.in.ua")
            failure_count = 0

def periodic_task():
    setup_browser()
    while True:
        get_air_alerts_status()
        time.sleep(15)



@app.get("/status")
@limiter.limit("100/10minutes")
def get_status(request: Request):
    return alert_status

@app.get("/region/{name}")
@limiter.limit("100/10minutes")
def get_region_status(request: Request, name: str):
    found = {region: status for region, status in alert_status.items() if name.lower() in region.lower()}
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
