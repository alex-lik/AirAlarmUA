
# ===== Stage 1: Build dependencies =====
FROM python:3.13-slim as builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --user -r requirements.txt


# ===== Stage 2: Final image =====
FROM python:3.13-slim

ENV PATH="/root/.local/bin:$PATH"
WORKDIR /app

# 🧩 Устанавливаем зависимости для Chromium
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-liberation libatk-bridge2.0-0 libnspr4 libnss3 libxss1 \
    libappindicator3-1 libasound2 libatk1.0-0 libcups2 libdbus-1-3 \
    libgdk-pixbuf2.0-0 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libgtk-3-0 wget curl unzip gnupg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 🛠 Копируем зависимости и проект
COPY --from=builder /root/.local /root/.local
COPY . .

# 🛡 Указываем путь к Chrome и Chromedriver
ENV CHROME_BIN="/usr/bin/chromium"
ENV CHROMEDRIVER_BIN="/usr/bin/chromedriver"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
