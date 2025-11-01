
import os
import time
from threading import Thread
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, Response, HTTPException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException, TimeoutException
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
driver = None
last_kyiv_status = None
failure_count = 0
MAX_FAILURES = 5

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

active_regions = Gauge("air_alert_regions_total",
                       "Количество регионов по статусу", ["status"])
update_timestamp = Gauge("air_alert_last_update_timestamp",
                         "Последнее обновление в формате UNIX-времени")


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
logger.add('./logs/today.log', level="ERROR",
           rotation="1 day", retention="10 days")



@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests"})


def check_label(label: str) -> bool:
    ukr_letters = set("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя")
    return bool(label) and any(l in ukr_letters for l in label)


def setup_browser():
    global driver
    if driver:
        try:
            # Проверяем, что драйвер еще жив
            driver.current_url
            return
        except (WebDriverException, TimeoutException):
            logger.warning("Драйвер не отвечает, перезапускаем...")
            close_browser()

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1024,768")
    options.add_argument("--timeout=120")  # Увеличиваем общий таймаут

    service = Service(log_path=os.devnull)
    driver = webdriver.Chrome(options=options, service=service)
    driver.set_page_load_timeout(30)  # Увеличиваем таймаут загрузки страницы
    driver.implicitly_wait(10)

    try:
        driver.get("https://alerts.in.ua")
        logger.info("Браузер успешно запущен и страница загружена")
    except Exception as e:
        logger.error(f"Не удалось загрузить страницу: {e}")
        raise


def close_browser():
    global driver
    if driver:
        try:
            driver.quit()
        except Exception as e:
            logger.warning(f"Ошибка при закрытии драйвера: {e}")
        finally:
            driver = None


def send_telegram_alert(message: str):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            requests.post(
                url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})
        except Exception as e:
            logger.error(f"Ошибка при отправке Telegram: {e}")


def get_air_alerts_status():
    global alert_status, last_update_time, driver, last_kyiv_status, failure_count
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            setup_browser()
            regions = {}

            # Добавляем попытку найти элементы с таймаутом
            try:
                elements = driver.find_elements(By.TAG_NAME, "text")
            except (WebDriverException, TimeoutException) as e:
                logger.warning(f"Проблема с поиском элементов (попытка {retry_count + 1}): {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)  # Пауза между попытками
                    # Перезапускаем браузер при проблемах
                    close_browser()
                continue

            if not elements:
                logger.warning(f"Элементы не найдены (попытка {retry_count + 1})")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)
                    close_browser()
                continue

            for el in elements:
                try:
                    label = el.text.strip()
                    if not check_label(label):
                        continue
                    class_attr = el.get_attribute("class")
                    is_alert = "active" in class_attr
                    regions[label] = is_alert
                except Exception as e:
                    logger.warning(f"Ошибка обработки элемента: {e}")
                    continue

            if not regions:
                logger.warning(f"Не получено данных о регионах (попытка {retry_count + 1})")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)
                    close_browser()
                continue

            alert_status = regions
            last_update_time = int(time.time())

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
            logger.info(f"Успешно обновлен статус {len(regions)} регионов")
            return  # Выходим при успехе

        except WebDriverException as e:
            retry_count += 1
            logger.error(f"Ошибка WebDriver (попытка {retry_count}/{max_retries}): {e}")
            close_browser()  # Принудительно закрываем при проблемах

            if retry_count < max_retries:
                time.sleep(5)  # Длинная пауза между попытками
        except Exception as e:
            retry_count += 1
            logger.error(f"Общая ошибка (попытка {retry_count}/{max_retries}): {e}")
            sentry_sdk.capture_exception(e)

            if retry_count < max_retries:
                time.sleep(5)
                close_browser()

    # Если все попытки неудачны
    failure_count += 1
    logger.error(f"Не удалось обновить статус после {max_retries} попыток")

    if failure_count >= MAX_FAILURES:
        send_telegram_alert(
            "❌ Проблемы с обновлением alerts.in.ua - требуется внимание")
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
