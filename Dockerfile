
# ===== Stage 1: Build dependencies =====
FROM python:3.13-slim as builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --user -r requirements.txt


# ===== Stage 2: Final image =====
FROM python:3.13-slim

ENV PATH="/root/.local/bin:$PATH"
WORKDIR /app

# 🛠 Копируем зависимости и проект
COPY --from=builder /root/.local /root/.local
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
