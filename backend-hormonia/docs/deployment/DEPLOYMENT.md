# Backend Deployment Guide

## 🚀 Overview

Guia completo para deploy do backend em produção.

**Plataformas Suportadas:**
- Railway (Recomendado)
- Docker / Docker Compose
- Kubernetes
- VPS (Ubuntu/Debian)

## ✅ Pre-Deployment Checklist

- [ ] Todas as variáveis de ambiente configuradas
- [ ] Database migrations aplicadas
- [ ] RLS policies testadas
- [ ] Redis configurado
- [ ] SSL/TLS certificates prontos
- [ ] Backup strategy definida
- [ ] Monitoring configurado
- [ ] Testes passando (pytest)

## 🚂 Railway (Recomendado)

### Setup

1. **Install Railway CLI**
```bash
npm install -g @railway/cli
railway login
```

2. **Create Project**
```bash
cd Backend
railway init
```

3. **Configure Services**

No Railway dashboard, adicione:
- PostgreSQL (ou conecte Supabase externo)
- Redis
- Backend service (Python)

4. **Set Environment Variables**

Via Railway UI ou CLI:
```bash
railway variables set SECRET_KEY=<value>
railway variables set DATABASE_URL=${{Postgres.DATABASE_URL}}
railway variables set REDIS_URL=${{Redis.REDIS_URL}}
railway variables set SUPABASE_URL=<value>
railway variables set SUPABASE_SERVICE_ROLE_KEY=<value>
railway variables set GOOGLE_API_KEY=<value>
railway variables set EVOLUTION_API_KEY=<value>
```

5. **Deploy**
```bash
railway up
```

### Railway Configuration

**railway.json:**
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 300,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

**Nixpacks Configuration (nixpacks.toml):**
```toml
[phases.setup]
nixPkgs = ["python313", "postgresql"]

[phases.install]
cmds = ["pip install -r requirements.txt"]

[phases.build]
cmds = ["alembic upgrade head"]

[start]
cmd = "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4"
```

### Railway Auto-Scaling

```bash
# Enable auto-scaling (via Railway UI)
# Min instances: 1
# Max instances: 5
# CPU threshold: 70%
# Memory threshold: 80%
```

## 🐳 Docker

### Dockerfile

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run migrations and start server
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env.production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: hormonia
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    restart: unless-stopped

  celery_worker:
    build: .
    command: celery -A app.celery_app worker --loglevel=info
    env_file:
      - .env.production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  celery_beat:
    build: .
    command: celery -A app.celery_app beat --loglevel=info
    env_file:
      - .env.production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### Deploy

```bash
# Build and run
docker-compose -f docker-compose.yml up -d

# View logs
docker-compose logs -f backend

# Stop
docker-compose down
```

## ☸️ Kubernetes

### Deployment

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
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: hormonia-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: hormonia-secrets
              key: redis-url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: hormonia-backend-service
spec:
  selector:
    app: hormonia-backend
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

## 🖥️ VPS (Ubuntu/Debian)

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.13 python3-pip python3-venv \
    postgresql-client redis-tools nginx certbot python3-certbot-nginx

# Create app user
sudo useradd -m -s /bin/bash hormonia
sudo su - hormonia
```

### 2. Application Setup

```bash
# Clone repo
git clone https://github.com/your-org/hormonia.git
cd hormonia/Backend

# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Edit with production values
```

### 3. Systemd Service

**/etc/systemd/system/hormonia.service:**
```ini
[Unit]
Description=Hormonia Backend API
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=hormonia
Group=hormonia
WorkingDirectory=/home/hormonia/hormonia/Backend
Environment="PATH=/home/hormonia/hormonia/Backend/venv/bin"
ExecStart=/home/hormonia/hormonia/Backend/venv/bin/uvicorn \
    app.main:app --host 0.0.0.0 --port 8000 --workers 4

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable hormonia
sudo systemctl start hormonia
sudo systemctl status hormonia
```

### 4. Nginx Reverse Proxy

**/etc/nginx/sites-available/hormonia:**
```nginx
server {
    listen 80;
    server_name api.hormonia.app;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/hormonia /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# SSL with Let's Encrypt
sudo certbot --nginx -d api.hormonia.app
```

## 🔒 Security Hardening

### Firewall (UFW)

```bash
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### Environment Secrets

**NEVER commit .env files!**

Use secrets management:
- Railway: Built-in secrets
- Docker: Docker secrets
- Kubernetes: Kubernetes secrets
- VPS: Encrypted vault (ansible-vault, pass)

### SSL/TLS

- **Railway**: Automatic HTTPS
- **Docker**: Use Traefik or nginx-proxy with Let's Encrypt
- **Kubernetes**: cert-manager
- **VPS**: Certbot (Let's Encrypt)

## 📊 Monitoring

### Health Checks

```bash
# Application health
curl https://api.hormonia.app/health

# Redis health
curl https://api.hormonia.app/api/v1/redis/health

# Database connection
psql $DATABASE_URL -c "SELECT 1"
```

### Logging

**Railway**: Automatic log aggregation

**Docker**:
```bash
docker-compose logs -f backend
```

**Kubernetes**:
```bash
kubectl logs -f deployment/hormonia-backend
```

**VPS**:
```bash
sudo journalctl -u hormonia -f
```

### Metrics

Configure Prometheus + Grafana:
- CPU usage
- Memory usage
- Request latency
- Error rates
- Database connections
- Redis operations

## 🔄 Database Migrations

```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Rollback
alembic downgrade -1
```

## 📦 Backup Strategy

### Database Backup

```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump $DATABASE_URL > /backups/hormonia_$DATE.sql
gzip /backups/hormonia_$DATE.sql

# Keep only last 30 days
find /backups -name "hormonia_*.sql.gz" -mtime +30 -delete
```

### Redis Backup

```bash
# Redis RDB backup
redis-cli -u $REDIS_URL BGSAVE
```

## 🔧 Performance Optimization

### Gunicorn/Uvicorn Workers

```bash
# Calculate workers: (2 x CPU cores) + 1
# 4 cores = 9 workers
uvicorn app.main:app --workers 9
```

### Connection Pooling

```python
# app/core/database.py
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

### Redis Configuration

```bash
# redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
```

## 🚨 Rollback Plan

### Railway

```bash
# Rollback to previous deployment
railway rollback
```

### Docker

```bash
# Deploy previous version
docker-compose pull backend:previous-tag
docker-compose up -d backend
```

### Kubernetes

```bash
# Rollback deployment
kubectl rollout undo deployment/hormonia-backend
```

## 📚 Post-Deployment

1. **Verify health checks** pass
2. **Test critical endpoints** (login, patient CRUD)
3. **Monitor logs** for errors
4. **Check performance metrics**
5. **Validate database connections**
6. **Test WhatsApp integration**
7. **Verify AI services working**

## 🆘 Troubleshooting

### Application won't start

```bash
# Check logs
docker-compose logs backend
# or
journalctl -u hormonia -n 50

# Verify environment
python scripts/validate_env.py

# Test DB connection
psql $DATABASE_URL -c "SELECT 1"
```

### High latency

```bash
# Check database
psql $DATABASE_URL -c "SELECT * FROM pg_stat_activity"

# Check Redis
redis-cli -u $REDIS_URL INFO

# Monitor application
curl https://api.hormonia.app/api/v1/enhanced/monitoring/dashboard
```

### Out of memory

```bash
# Check memory usage
docker stats
# or
free -h
top

# Reduce workers
uvicorn app.main:app --workers 2
```

## 📞 Support

- **Logs**: Primeiro lugar para diagnóstico
- **Health endpoints**: `/health`, `/api/v1/redis/health`
- **Documentation**: Consulte docs técnicos
- **Monitoring**: Use dashboards de monitoring

---

**Sistema Hormonia Backend** - Production-ready deployment guide