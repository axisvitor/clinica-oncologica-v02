# Railway Debug Dockerfile - For identifying deployment issues
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Create a debug script
RUN echo '#!/bin/bash\necho "=== Railway Debug Information ==="\necho "Python version: $(python --version)"\necho "Working directory: $(pwd)"\necho "Python path: $PYTHONPATH"\necho "Contents of /app:"\nls -la /app\necho "Contents of app directory:"\nls -la app/ || echo "app directory not found"\necho "Testing imports..."\npython -c "import sys; print(\"Python sys.path:\", sys.path)"\npython -c "try: import app; print(\"app module import: SUCCESS\"); except Exception as e: print(\"app module import: FAILED -\", e)"\npython -c "try: import app.config; print(\"app.config import: SUCCESS\"); except Exception as e: print(\"app.config import: FAILED -\", e)"\npython -c "try: import app.agents.base; print(\"app.agents.base import: SUCCESS\"); except Exception as e: print(\"app.agents.base import: FAILED -\", e)"\npython -c "try: from app.agents.base import BaseAgent, AgentCapabilities; print(\"BaseAgent, AgentCapabilities import: SUCCESS\"); except Exception as e: print(\"BaseAgent, AgentCapabilities import: FAILED -\", e)"\necho "=== End Debug Info ==="\necho "Starting minimal server..."\nuvicorn app.minimal_main:app --host 0.0.0.0 --port ${PORT:-8000}' > /app/debug_start.sh && chmod +x /app/debug_start.sh

# Expose port
EXPOSE 8000

# Use debug startup script
CMD ["/app/debug_start.sh"]