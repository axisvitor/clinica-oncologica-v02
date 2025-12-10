# Backend Universal Dockerfile
# Supports: API, Celery Worker, Celery Beat
FROM python:3.13-slim

ARG APP_SRC=.

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY ${APP_SRC}/requirements.txt ./requirements.txt

# Upgrade pip and install dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ${APP_SRC}/ .

# Ensure scripts are executable
RUN chmod +x scripts/entrypoint.sh scripts/healthcheck.sh

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PASSLIB_BUILTIN_BCRYPT=enabled \
    PATH="/app/scripts:${PATH}"

EXPOSE 8000

# Universal Healthcheck
# Relies on SERVICE_TYPE env var (default: api)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /app/scripts/healthcheck.sh

# Entrypoint script handles the start command
ENTRYPOINT ["/app/scripts/entrypoint.sh"]

# Default command (can be overridden by Railway Start Command)
# Options: "api", "worker", "beat"
CMD ["api"]