# Backend Dockerfile - Python 3.13 + Node.js for hybrid dependencies
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Node.js for bcrypt/supabase-js
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    bash \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy and install dependencies (Python + Node.js)
COPY requirements.txt package.json ./
RUN pip install --no-cache-dir --upgrade pip==24.3.* && \
    pip install --no-cache-dir -r requirements.txt && \
    pip cache purge && \
    npm install --omit=dev

# Copy application code
COPY . .

# Set proper ownership
RUN chown -R appuser:appuser /app

# Set environment variables for Railway
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PORT=8000
# Force passlib to use builtin bcrypt to avoid bug
ENV PASSLIB_BUILTIN_BCRYPT=enabled

# Health check for Railway
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Expose port (Railway will set PORT env var)
EXPOSE ${PORT:-8000}

# Switch to non-root user
USER appuser

# Start server with gunicorn + uvicorn workers for production
CMD gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info