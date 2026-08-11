FROM python:3.12-slim

# Python settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application source
COPY . .

# Upgrade pip tools
RUN pip install --upgrade pip setuptools wheel

# Install common-adapters package from pyproject.toml
RUN pip install --no-cache-dir .

# Install relay-specific dependencies
RUN pip install --no-cache-dir -r requirements-relay.txt

# Azure App Service Container listens on dynamic port
EXPOSE 8000

# Start Unified Relay
CMD ["sh","-c","gunicorn -k uvicorn.workers.UvicornWorker common_adapters.relay.unified_relay:app --bind 0.0.0.0:${PORT:-8000} --timeout 120 --workers 1"]
