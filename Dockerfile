FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Copy files
COPY . .

# Install relay dependencies
RUN pip install --no-cache-dir -r requirements-relay.txt

# Install common-adapters package from pyproject.toml
RUN pip install --no-cache-dir .

# Make startup script executable
RUN chmod +x startup-relay.sh

EXPOSE 8000

CMD ["./startup-relay.sh"]
