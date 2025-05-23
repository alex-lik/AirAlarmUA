import os
from loguru import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


logger.add('./logs/today.log', level="ERROR", rotation="1 day", retention="10 days")

def _check_label(label: str) -> bool:
    if not label:
        return False
    ukr_letters = set("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя")
    return any(l in ukr_letters for l in label)

def get_air_alerts_status():
    options = Options()
    options.add_argument("--window-size=1024,768")
    options.add_argument("--headless")  # включи, если не нужен интерфейс
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    service = Service(log_path=os.devnull)
    driver = webdriver.Chrome(options=options, service=service)

    try:
        driver.get("https://alerts.in.ua")
        driver.implicitly_wait(10)

        regions = {}
        elements = driver.find_elements(By.TAG_NAME, "text")

        for el in elements:
            label = el.text.strip()
            if not _check_label(label):
                continue

            class_attr = el.get_attribute("class")
            is_alert = "active" in class_attr
            regions[label] = is_alert

        return regions

    except Exception as e:
        logger.error(e)
        return {}

    finally:
        driver.quit()


if __name__ == "__main__":
    alerts = get_air_alerts_status()
    print(alerts)
    for region, status in alerts.items():
        if status:
            logger.warning(f"🚨 {region}: 'ТРЕВОГА'")
        else:
            logger.success(f"✅ {region}: 'спокойно'")
