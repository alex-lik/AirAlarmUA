
import os
from fastapi import FastAPI
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from loguru import logger
from threading import Thread
import time
import sentry_sdk

SENTRY_DSN = os.getenv("SENTRY_DSN")

sentry_sdk.init(dsn=SENTRY_DSN, send_default_pii=True)

logger.add('./logs/today.log', level="ERROR", rotation="1 day", retention="10 days")

app = FastAPI()
alert_status = {}

def check_label(label: str) -> bool:
    if not label:
        return False
    ukr_letters = set("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя")
    return any(l in ukr_letters for l in label)

def get_air_alerts_status():
    global alert_status
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1024,768")
    service = Service(log_path=os.devnull)
    driver = webdriver.Chrome(options=options, service=service)

    try:
        driver.get("https://alerts.in.ua")
        driver.implicitly_wait(10)

        regions = {}
        elements = driver.find_elements(By.TAG_NAME, "text")

        for el in elements:
            label = el.text.strip()
            if not check_label(label):
                continue

            class_attr = el.get_attribute("class")
            is_alert = "active" in class_attr
            regions[label] = is_alert

        alert_status = regions
        logger.success("Данные тревоги обновлены.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении тревог: {e}")
    finally:
        driver.quit()

def periodic_task():
    while True:
        get_air_alerts_status()
        time.sleep(600)  # каждые 10 минут

@app.on_event("startup")
def startup_event():
    Thread(target=periodic_task, daemon=True).start()

@app.get("/status")
def get_status():
    return alert_status


@app.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1 / 0