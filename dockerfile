FROM python:3.11 AS builder

WORKDIR /build
COPY requirements.txt /build/requirements.txt
RUN python -m pip install --upgrade pip \
  && pip wheel --no-cache-dir --wheel-dir /build/wheels -r /build/requirements.txt

FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN useradd -m -u 10001 appuser

WORKDIR /app
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
  && rm -rf /wheels

COPY app.py /app/app.py
COPY weather_service.py /app/weather_service.py

USER appuser

EXPOSE 8080

CMD ["python", "app.py"]
