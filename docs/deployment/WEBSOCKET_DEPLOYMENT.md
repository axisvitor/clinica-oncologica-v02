# WebSocket Deployment Guide
**Version**: 2.0 (Unified Implementation)
**Date**: 2025-11-07
**Target**: Production Environment

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Environment Configuration](#environment-configuration)
4. [Single Instance Deployment](#single-instance-deployment)
5. [Multi-Instance Deployment](#multi-instance-deployment)
6. [Redis Configuration](#redis-configuration)
7. [Health Checks](#health-checks)
8. [Monitoring & Metrics](#monitoring--metrics)
9. [Troubleshooting](#troubleshooting)
10. [Rollback Plan](#rollback-plan)

---

## Overview

The Unified WebSocket Manager supports both single-instance and multi-instance (horizontally scaled) deployments. This guide covers production deployment scenarios.

**Key Features**:
- ✅ Automatic lifecycle management
- ✅ Heartbeat monitoring (30s intervals)
- ✅ Automatic cleanup (60s intervals)
- ✅ Horizontal scaling via Redis Pub/Sub
- ✅ Graceful shutdown with connection cleanup

---

## Prerequisites

### Required

- **Python**: 3.9+
- **FastAPI**: 0.100+
- **Redis**: 6.0+ (for multi-instance deployment)
- **PostgreSQL**: 13+ (for authentication)

### Recommended

- **NGINX**: Reverse proxy with WebSocket support
- **Systemd**: Process management
- **Docker**: Container deployment (optional)
- **Kubernetes**: Orchestration (for multi-instance)

---

## Environment Configuration

### Environment Variables

```bash
# Required
DATABASE_URL="postgresql://user:pass@localhost:5432/hormonia"
SECRET_KEY="your-secret-key-here"

# WebSocket Configuration
WEBSOCKET_HEARTBEAT_INTERVAL=30  # seconds
WEBSOCKET_CLEANUP_INTERVAL=60    # seconds
WEBSOCKET_MAX_CONNECTIONS_PER_USER=5

# Redis (Required for multi-instance)
REDIS_URL="redis://localhost:6379/0"

# Firebase Authentication
FIREBASE_PROJECT_ID="your-project-id"
FIREBASE_SERVICE_ACCOUNT_PATH="/path/to/service-account.json"

# JWT Configuration
JWT_ALGORITHM="HS256"
JWT_SECRET_KEY="your-jwt-secret"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Optional: Monitoring
ENABLE_WEBSOCKET_METRICS=true
METRICS_PORT=9090
```

### Configuration File

Create `config/websocket.yaml`:

```yaml
websocket:
  heartbeat_interval: 30
  cleanup_interval: 60
  max_connections_per_user: 5
  max_message_size: 1048576  # 1MB
  ping_timeout: 60

redis_pubsub:
  enabled: true
  channel_prefix: "ws"
  reconnect_attempts: 3
  reconnect_delay: 5

monitoring:
  enabled: true
  metrics_interval: 60
  log_level: "INFO"
```

---

## Single Instance Deployment

### 1. Application Setup

```bash
# Clone repository
git clone <repo-url>
cd clinica-oncologica-v02/backend-hormonia

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head
```

### 2. Systemd Service

Create `/etc/systemd/system/hormonia-backend.service`:

```ini
[Unit]
Description=Hormonia Backend API
After=network.target postgresql.service

[Service]
Type=notify
User=hormonia
Group=hormonia
WorkingDirectory=/opt/hormonia/backend-hormonia
Environment="PATH=/opt/hormonia/venv/bin"
EnvironmentFile=/opt/hormonia/.env

ExecStart=/opt/hormonia/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --lifespan on

# Graceful shutdown
TimeoutStopSec=30
KillMode=mixed
KillSignal=SIGTERM

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 3. NGINX Configuration

Create `/etc/nginx/sites-available/hormonia`:

```nginx
upstream hormonia_backend {
    server localhost:8000;
}

map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

server {
    listen 80;
    server_name api.hormonia.example.com;

    # WebSocket endpoint
    location /ws {
        proxy_pass http://hormonia_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket timeouts
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # Regular API endpoints
    location / {
        proxy_pass http://hormonia_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 4. Start Services

```bash
# Enable and start services
sudo systemctl enable hormonia-backend
sudo systemctl start hormonia-backend

# Check status
sudo systemctl status hormonia-backend

# View logs
sudo journalctl -u hormonia-backend -f
```

---

## Multi-Instance Deployment

### Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │────▶│  NGINX   │────▶│Instance 1│
│          │     │  (LB)    │  ┌─▶│   App    │
└──────────┘     └──────────┘  │  └────┬─────┘
                                │       │
                                │  ┌────▼─────┐
                                ├─▶│Instance 2│
                                │  │   App    │
                                │  └────┬─────┘
                                │       │
                                │  ┌────▼─────┐
                                └─▶│Instance 3│
                                   │   App    │
                                   └────┬─────┘
                                        │
                                   ┌────▼─────┐
                                   │  Redis   │
                                   │ Pub/Sub  │
                                   └──────────┘
```

### 1. Redis Setup

```bash
# Install Redis
sudo apt-get install redis-server

# Configure Redis
sudo vi /etc/redis/redis.conf
```

**Redis Configuration**:
```conf
bind 0.0.0.0
port 6379
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence (optional for pub/sub)
save 900 1
save 300 10
save 60 10000
```

### 2. Docker Compose Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  backend_1:
    build: ./backend-hormonia
    environment:
      - REDIS_URL=redis://redis:6379/0
      - INSTANCE_ID=backend_1
    ports:
      - "8001:8000"
    depends_on:
      - redis
      - postgres

  backend_2:
    build: ./backend-hormonia
    environment:
      - REDIS_URL=redis://redis:6379/0
      - INSTANCE_ID=backend_2
    ports:
      - "8002:8000"
    depends_on:
      - redis
      - postgres

  backend_3:
    build: ./backend-hormonia
    environment:
      - REDIS_URL=redis://redis:6379/0
      - INSTANCE_ID=backend_3
    ports:
      - "8003:8000"
    depends_on:
      - redis
      - postgres

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - backend_1
      - backend_2
      - backend_3

  postgres:
    image: postgres:13
    environment:
      - POSTGRES_DB=hormonia
      - POSTGRES_USER=hormonia
      - POSTGRES_PASSWORD=secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  redis_data:
  postgres_data:
```

### 3. NGINX Load Balancer

```nginx
upstream hormonia_backends {
    # Sticky sessions based on IP (optional)
    ip_hash;

    server backend_1:8000;
    server backend_2:8000;
    server backend_3:8000;
}

map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

server {
    listen 80;
    server_name api.hormonia.example.com;

    location /ws {
        proxy_pass http://hormonia_backends;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;

        # Important: Allow long-lived connections
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_connect_timeout 10s;

        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location / {
        proxy_pass http://hormonia_backends;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. Kubernetes Deployment

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hormonia-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: hormonia-backend
  template:
    metadata:
      labels:
        app: hormonia-backend
    spec:
      containers:
      - name: backend
        image: hormonia/backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379/0"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: hormonia-backend
spec:
  selector:
    app: hormonia-backend
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## Redis Configuration

### Pub/Sub Channels

The system uses these Redis channels:

| Channel | Purpose | Example |
|---------|---------|---------|
| `ws:broadcast` | Global broadcasts | System announcements |
| `ws:room:{room_id}` | Room messages | Patient room updates |
| `ws:user:{user_id}` | User messages | Multi-device notifications |
| `ws:heartbeat` | Health checks | Instance monitoring |

### Redis Monitoring

```bash
# Monitor pub/sub activity
redis-cli PUBSUB CHANNELS ws:*

# Monitor specific channel
redis-cli SUBSCRIBE ws:broadcast

# Check connections
redis-cli CLIENT LIST
```

---

## Health Checks

### Liveness Probe

Check if application is running:

```python
# app/api/health.py
@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}
```

### Readiness Probe

Check if ready to serve traffic:

```python
@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    try:
        # Check database
        db.execute("SELECT 1")

        # Check Redis
        redis_manager = get_redis_manager()
        redis_client = await redis_manager.get_async_client()
        await redis_client.ping()

        # Check WebSocket manager
        ws_manager = get_websocket_manager()
        if not ws_manager._started:
            raise Exception("WebSocket manager not started")

        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Not ready: {e}")
```

### WebSocket Health

```python
@router.get("/health/websocket")
async def websocket_health():
    manager = get_websocket_manager()
    stats = manager.get_connection_stats()

    return {
        "status": "healthy",
        "connections": stats["total_connections"],
        "authenticated": stats["authenticated_connections"],
        "uptime": stats["uptime"]
    }
```

---

## Monitoring & Metrics

### Prometheus Metrics

```python
from prometheus_client import Counter, Gauge, Histogram

# Metrics
websocket_connections = Gauge(
    'websocket_active_connections',
    'Number of active WebSocket connections'
)

websocket_messages_sent = Counter(
    'websocket_messages_sent_total',
    'Total messages sent via WebSocket'
)

websocket_latency = Histogram(
    'websocket_message_latency_seconds',
    'Message delivery latency'
)

# Update metrics
def update_metrics():
    manager = get_websocket_manager()
    stats = manager.get_connection_stats()

    websocket_connections.set(stats['total_connections'])
```

### Grafana Dashboard

Key metrics to track:

- Active connections (gauge)
- Messages per second (rate)
- Message latency (histogram)
- Authentication success/failure rate
- Connections by state/role
- Room occupancy
- Heartbeat response time

---

## Troubleshooting

### Common Issues

#### 1. Connections Not Establishing

**Symptoms**: WebSocket connections fail immediately

**Solutions**:
```bash
# Check NGINX WebSocket config
grep -A 10 "location /ws" /etc/nginx/sites-enabled/hormonia

# Check firewall
sudo ufw status
sudo ufw allow 8000/tcp

# Check application logs
sudo journalctl -u hormonia-backend -f
```

#### 2. Connections Dropping Frequently

**Symptoms**: Connections close after 30-60 seconds

**Solutions**:
- Increase `proxy_read_timeout` in NGINX
- Check heartbeat implementation
- Review cleanup interval settings

#### 3. Redis Pub/Sub Not Working

**Symptoms**: Messages not broadcasting across instances

**Solutions**:
```bash
# Check Redis connectivity
redis-cli -h <redis-host> ping

# Monitor pub/sub
redis-cli SUBSCRIBE ws:*

# Check Redis logs
sudo tail -f /var/log/redis/redis-server.log
```

#### 4. High Memory Usage

**Symptoms**: Memory grows continuously

**Solutions**:
- Check for connection leaks
- Review cleanup task execution
- Monitor stale connection cleanup
- Adjust `max_connections_per_user`

---

## Rollback Plan

### Immediate Rollback

If critical issues arise:

```bash
# 1. Stop new deployment
sudo systemctl stop hormonia-backend

# 2. Checkout previous version
git checkout <previous-commit>

# 3. Restore legacy files (if needed)
git checkout <previous-commit> -- backend-hormonia/app/services/websocket_manager.py

# 4. Restart service
sudo systemctl start hormonia-backend

# 5. Verify
curl http://localhost:8000/health
```

### Gradual Rollback

For multi-instance deployment:

```bash
# Roll back one instance at a time
kubectl rollout undo deployment/hormonia-backend --to-revision=<revision>

# Monitor
kubectl rollout status deployment/hormonia-backend
```

---

## Performance Tuning

### Recommended Settings

**For up to 1,000 connections**:
```yaml
websocket:
  heartbeat_interval: 30
  cleanup_interval: 60
  max_connections_per_user: 5

uvicorn:
  workers: 4
  backlog: 2048
```

**For 1,000-10,000 connections**:
```yaml
websocket:
  heartbeat_interval: 60
  cleanup_interval: 120
  max_connections_per_user: 10

uvicorn:
  workers: 8
  backlog: 4096

nginx:
  worker_connections: 4096
```

---

## Security Checklist

- [ ] SSL/TLS enabled (wss://)
- [ ] Authentication required for all connections
- [ ] Rate limiting implemented
- [ ] CORS configured properly
- [ ] Firewall rules configured
- [ ] Redis protected with password
- [ ] Database credentials secured
- [ ] Secrets in environment variables
- [ ] Regular security audits scheduled

---

**Last Updated**: 2025-11-07
**Maintained By**: DevOps Team
**Version**: 2.0 (Unified Implementation)
