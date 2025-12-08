FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy exporter code
COPY app_exporter.py .

# Expose metrics port
EXPOSE 9100

# Run exporter
CMD ["python", "app_exporter.py"]
