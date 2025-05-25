
# Этап 1: установка зависимостей
FROM python:3.13-slim as builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --user -r requirements.txt

# Этап 2: финальный образ
FROM python:3.13-slim

ENV PATH=/root/.local/bin:$PATH
WORKDIR /app

# Копируем только нужное
COPY --from=builder /root/.local /root/.local
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
