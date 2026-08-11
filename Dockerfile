FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements-relay.txt
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["gunicorn","-k","uvicorn.workers.UvicornWorker","common_adapters.relay.unified_relay:app","--bind","0.0.0.0:8000","--timeout","120","--workers","1"]
