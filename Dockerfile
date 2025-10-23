# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install shared library first
COPY sigmatiq-shared ./sigmatiq-shared
RUN pip install --no-cache-dir ./sigmatiq-shared

# Install Python dependencies
COPY sigmatiq-card-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY sigmatiq-card-api/sigmatiq_card_api ./sigmatiq_card_api

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8007

# Expose the port
EXPOSE 8007

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8007/healthz', timeout=5)"

# Run the application
CMD ["uvicorn", "sigmatiq_card_api.app:app", "--host", "0.0.0.0", "--port", "8007"]
