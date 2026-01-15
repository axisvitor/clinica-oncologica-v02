FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Install system dependencies and apply security updates
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    build-essential \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    libmagic1 \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (as root, then switch to non-root user)
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install --root-user-action=ignore -r requirements.txt

# Create non-root user for security (CVE mitigation best practice)
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --timeout-keep-alive 75"]

