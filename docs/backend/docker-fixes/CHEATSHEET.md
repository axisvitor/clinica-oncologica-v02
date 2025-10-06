# 🚀 Docker Quick Reference - Backend Hormonia

Comandos essenciais e referências rápidas para gerenciamento Docker.

---

## 📦 Build & Deploy

### Build Local
```bash
# Build padrão
docker build -t hormonia-backend:latest .

# Build com BuildKit (mais rápido)
DOCKER_BUILDKIT=1 docker build -t hormonia-backend:latest .

# Build sem cache
docker build --no-cache -t hormonia-backend:latest .

# Build com debug
docker build --progress=plain -t hormonia-backend:latest .
```

### Run Container
```bash
# Run básico
docker run -p 8000:8000 hormonia-backend:latest

# Run com variáveis de ambiente
docker run -p 8000:8000 -e PORT=8000 -e DEBUG=true hormonia-backend:latest

# Run com .env file
docker run -p 8000:8000 --env-file .env hormonia-backend:latest

# Run em background (detached)
docker run -d -p 8000:8000 --name hormonia-api hormonia-backend:latest

# Run com volume (desenvolvimento)
docker run -p 8000:8000 -v $(pwd)/app:/app/app hormonia-backend:latest
```

---

## 🐙 Docker Compose

### Comandos Básicos
```bash
# Iniciar todos os serviços
docker-compose up -d

# Iniciar serviços específicos
docker-compose up -d redis celery-worker

# Parar serviços
docker-compose down

# Parar e remover volumes (⚠️ remove dados)
docker-compose down -v

# Restart serviço específico
docker-compose restart celery-worker

# Ver logs
docker-compose logs -f

# Ver logs de serviço específico
docker-compose logs -f celery-worker

# Ver status
docker-compose ps

# Executar comando em serviço
docker-compose exec celery-worker bash

# Rebuild e restart
docker-compose up -d --build
```

### Scaling
```bash
# Escalar workers
docker-compose up -d --scale celery-worker=4

# Ver workers rodando
docker-compose ps celery-worker
```

---

## 🔍 Debugging

### Logs
```bash
# Logs de container específico
docker logs hormonia-backend

# Seguir logs em tempo real
docker logs -f hormonia-backend

# Últimas 100 linhas
docker logs --tail 100 hormonia-backend

# Logs com timestamp
docker logs --timestamps hormonia-backend
```

### Shell Access
```bash
# Bash no container
docker exec -it hormonia-backend bash

# Python shell
docker exec -it hormonia-backend python

# Redis CLI
docker-compose exec redis redis-cli -a $(cat secrets/redis_password.txt)

# Celery inspect
docker-compose exec celery-worker celery -A app.celery_app inspect active
```

### Health Check
```bash
# Ver status de health
docker inspect hormonia-backend | grep -A 10 Health

# Ver todos os healthchecks
docker ps --format "table {{.Names}}\t{{.Status}}"

# Testar healthcheck manualmente
docker exec hormonia-backend wget --spider http://localhost:8000/health
```

---

## 🧹 Limpeza

### Containers
```bash
# Parar todos os containers
docker stop $(docker ps -aq)

# Remover containers parados
docker container prune -f

# Remover container específico
docker rm hormonia-backend

# Forçar remoção de container rodando
docker rm -f hormonia-backend
```

### Imagens
```bash
# Remover imagens não utilizadas
docker image prune -a -f

# Remover imagem específica
docker rmi hormonia-backend:latest

# Ver tamanho das imagens
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
```

### Volumes
```bash
# Listar volumes
docker volume ls

# Remover volumes não utilizados
docker volume prune -f

# Remover volume específico
docker volume rm backend-hormonia_redis_data
```

### Sistema Completo
```bash
# Limpeza completa (⚠️ cuidado!)
docker system prune -a --volumes -f

# Ver espaço usado pelo Docker
docker system df

# Ver espaço detalhado
docker system df -v
```

---

## 🔐 Secrets & Security

### Redis Password
```bash
# Ver senha do Redis
cat backend-hormonia/secrets/redis_password.txt

# Gerar nova senha
openssl rand -base64 32 > backend-hormonia/secrets/redis_password.txt

# Testar conexão com senha
docker-compose exec redis redis-cli -a $(cat secrets/redis_password.txt) PING
```

### Flower Credentials
```bash
# Ver credenciais do Flower
grep FLOWER_ backend-hormonia/.env

# Acessar Flower
open http://localhost:5555/flower
# Usuário: admin
# Senha: valor de FLOWER_PASSWORD no .env
```

---

## 📊 Monitoring

### Resource Usage
```bash
# Ver uso de recursos em tempo real
docker stats

# Ver uso de recurso específico
docker stats hormonia-backend

# Ver uso sem stream
docker stats --no-stream

# Formato customizado
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

### Network
```bash
# Listar networks
docker network ls

# Inspecionar network
docker network inspect backend-hormonia_cache-network

# Ver containers em uma network
docker network inspect backend-hormonia_app-network --format '{{range .Containers}}{{.Name}} {{end}}'
```

### Processes
```bash
# Ver processos rodando no container
docker top hormonia-backend

# Ver processos de todos os containers
docker-compose top
```

---

## 🧪 Testing

### Health Checks
```bash
# Testar endpoint de health
curl http://localhost:8000/health

# Testar com verbose
curl -v http://localhost:8000/health

# Dentro do container
docker exec hormonia-backend curl http://localhost:8000/health
```

### Redis
```bash
# Ping Redis
docker-compose exec redis redis-cli -a $(cat secrets/redis_password.txt) PING

# Benchmark Redis
docker-compose exec redis redis-benchmark -a $(cat secrets/redis_password.txt) -q

# Ver info do Redis
docker-compose exec redis redis-cli -a $(cat secrets/redis_password.txt) INFO
```

### Celery
```bash
# Listar workers ativos
docker-compose exec celery-worker celery -A app.celery_app inspect active

# Ver stats dos workers
docker-compose exec celery-worker celery -A app.celery_app inspect stats

# Executar task de teste
docker-compose exec celery-worker celery -A app.celery_app call app.tasks.test_task
```

---

## 🚀 Railway Deploy

### Comandos
```bash
# Login no Railway
railway login

# Link com projeto
railway link

# Ver variáveis de ambiente
railway variables

# Adicionar variável
railway variables set KEY=value

# Ver logs
railway logs

# Deploy manual
railway up
```

### Debug no Railway
```bash
# Build com debug Dockerfile
railway up --dockerfile railway-debug.dockerfile

# Ver deployment logs
railway logs --deployment <deployment-id>
```

---

## 🔧 Troubleshooting

### Container não inicia
```bash
# Ver logs completos
docker logs hormonia-backend

# Ver últimos erros
docker logs --tail 50 hormonia-backend 2>&1 | grep -i error

# Executar com TTY
docker run -it hormonia-backend:latest bash
```

### Port já em uso
```bash
# Ver quem está usando a porta
lsof -i :8000
# ou
netstat -ano | findstr :8000

# Matar processo
kill -9 <PID>
```

### Network issues
```bash
# Ver networks
docker network ls

# Inspecionar network
docker network inspect <network-name>

# Recriar network
docker network rm <network-name>
docker-compose up -d
```

### Volume permission issues
```bash
# Ver permissões
docker exec hormonia-backend ls -la /app

# Corrigir permissões (se necessário)
docker exec -u root hormonia-backend chown -R appuser:appuser /app
```

---

## 📝 One-Liners Úteis

```bash
# Ver todas as imagens ordenadas por tamanho
docker images --format "{{.Repository}}:{{.Tag}}\t{{.Size}}" | sort -k2 -h

# Remover containers com status "exited"
docker ps -a | grep Exit | cut -d ' ' -f 1 | xargs docker rm

# Remover imagens "<none>"
docker rmi $(docker images -f "dangling=true" -q)

# Ver IP de todos os containers
docker ps -q | xargs docker inspect --format '{{.Name}} - {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'

# Backup de volume
docker run --rm -v backend-hormonia_redis_data:/data -v $(pwd):/backup alpine tar czf /backup/redis-backup.tar.gz -C /data .

# Restore de volume
docker run --rm -v backend-hormonia_redis_data:/data -v $(pwd):/backup alpine tar xzf /backup/redis-backup.tar.gz -C /data

# Ver uso de memória por container
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" | sort -k2 -h

# Executar comando em todos os containers de um compose
docker-compose ps -q | xargs -I {} docker exec {} echo "Hello from {}"
```

---

## 🎯 Environment Variables Essenciais

```bash
# Docker
DOCKER_BUILDKIT=1                    # Habilitar BuildKit
COMPOSE_DOCKER_CLI_BUILD=1          # BuildKit no Compose

# Application
PORT=8000                            # Porta da aplicação
DEBUG=false                          # Debug mode
WORKERS=4                            # Número de workers Uvicorn

# Database
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db

# Redis
REDIS_PASSWORD=<gerado-openssl>
CELERY_BROKER_URL=redis://:pass@redis:6379/0

# Flower
FLOWER_USER=admin
FLOWER_PASSWORD=<gerado-openssl>

# Firebase
FIREBASE_PROJECT_ID=<project-id>
FIREBASE_PRIVATE_KEY=<base64-key>

# Monitoring
SENTRY_DSN=<sentry-dsn>
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318
```

---

## 📚 Referências Rápidas

### Dockerfile Syntax
```dockerfile
# Multi-stage build
FROM python:3.13-slim AS builder
FROM python:3.13-slim

# Build arguments
ARG PORT=8000
ENV PORT=$PORT

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD wget --spider http://localhost:${PORT}/health || exit 1

# User
USER appuser

# Entrypoint vs CMD
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app"]
```

### docker-compose.yml Syntax
```yaml
# Networks
networks:
  backend:
    driver: bridge
    internal: true

# Volumes
volumes:
  data:
    driver: local

# Secrets
secrets:
  password:
    file: ./secrets/password.txt

# Resource limits
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 1G
    reservations:
      cpus: '0.5'
      memory: 512M

# Healthcheck
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s

# Dependencies
depends_on:
  redis:
    condition: service_healthy
```

---

**Última atualização:** 2025-10-05
**Versão:** 1.0.0
