# Flower - Celery Monitoring UI
FROM python:3.11-slim

LABEL maintainer="DevOps Team"
LABEL description="Flower - Real-time Celery monitoring"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir \
    flower==2.0.1 \
    celery[redis]==5.3.4 \
    redis==5.0.1 \
    prometheus-client==0.19.0

# Create non-root user
RUN useradd -m -u 1000 flower && \
    chown -R flower:flower /app

USER flower

# Environment variables
ENV FLOWER_PORT=5555
ENV FLOWER_BROKER_API=redis://redis:6379/0
ENV FLOWER_PERSISTENT=true
ENV FLOWER_DB=/app/flower.db
ENV FLOWER_MAX_TASKS=10000
ENV FLOWER_PURGE_OFFLINE_WORKERS=60

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5555/healthcheck || exit 1

# Expose Flower port
EXPOSE 5555

# Start Flower with authentication
CMD ["celery", \
     "--broker=${CELERY_BROKER_URL}", \
     "flower", \
     "--port=${FLOWER_PORT}", \
     "--basic_auth=${FLOWER_BASIC_AUTH}", \
     "--max_tasks=${FLOWER_MAX_TASKS}", \
     "--persistent=${FLOWER_PERSISTENT}", \
     "--db=${FLOWER_DB}", \
     "--purge_offline_workers=${FLOWER_PURGE_OFFLINE_WORKERS}"]
