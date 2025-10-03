# Backend Dockerfile - Python 3.13 with Bcrypt Fix
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies with Railway optimizations
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy and install Python dependencies first (for Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==24.3.* && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade bcrypt==4.1.2 passlib==1.7.4 && \
    pip cache purge

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

# Start server directly with uvicorn
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'