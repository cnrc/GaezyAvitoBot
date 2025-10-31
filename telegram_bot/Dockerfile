# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Копируем только необходимые файлы для установки зависимостей
COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

# Копируем только нужные исходники сервиса
COPY app /app/app
COPY run.py /app/run.py

ENV PYTHONPATH=/app

CMD ["python", "run.py"]












