# 🚀 Guia de Implementação - Correções Docker

Este guia fornece instruções passo a passo para implementar as correções identificadas no relatório de revisão Docker.

---

## 📋 Pré-requisitos

- [ ] Docker Engine 20.10+ instalado
- [ ] Docker Compose 2.0+ instalado
- [ ] Git configurado
- [ ] Acesso ao repositório do projeto
- [ ] Credenciais de produção (Firebase, Supabase, etc.)

---

## 🔄 Plano de Implementação

### Fase 1: Correções Críticas (1-2 dias)

#### 1.1. Backup dos Arquivos Atuais

```bash
# Criar branch para implementação
git checkout -b feat/docker-improvements

# Backup dos arquivos originais
mkdir -p backups
cp backend-hormonia/Dockerfile backups/Dockerfile.backup
cp backend-hormonia/docker-compose.yml backups/docker-compose.yml.backup
cp backend-hormonia/railway-debug.dockerfile backups/railway-debug.dockerfile.backup
cp backend-hormonia/.dockerignore backups/.dockerignore.backup
```

#### 1.2. Implementar Multi-Stage Build

```bash
# Copiar novo Dockerfile otimizado
cp docs/backend/docker-fixes/Dockerfile.fixed backend-hormonia/Dockerfile

# Testar build local
cd backend-hormonia
docker build -t hormonia-backend:test .

# Verificar tamanho da imagem
docker images hormonia-backend:test
# Esperado: ~300MB (redução de ~60% vs ~800MB anterior)
```

#### 1.3. Corrigir Healthcheck

O novo Dockerfile já inclui healthcheck com `wget`. Testar:

```bash
# Executar container
docker run -d --name hormonia-test -p 8000:8000 hormonia-backend:test

# Verificar healthcheck
docker inspect hormonia-test | grep -A 10 Health

# Aguardar 90s (start-period) e verificar status
sleep 90
docker ps --filter "name=hormonia-test"
# Status deve ser "healthy"

# Limpar
docker stop hormonia-test
docker rm hormonia-test
```

#### 1.4. Atualizar Railway Debug Dockerfile

```bash
# Copiar versão corrigida
cp docs/backend/docker-fixes/railway-debug.dockerfile.fixed backend-hormonia/railway-debug.dockerfile

# Testar build
docker build -f railway-debug.dockerfile -t hormonia-debug:test .

# Executar e verificar logs de debug
docker run -p 8000:8000 -e PORT=8000 hormonia-debug:test
```

---

### Fase 2: Segurança (2-3 dias)

#### 2.1. Configurar Docker Secrets para Redis

```bash
# Criar diretório de secrets
mkdir -p backend-hormonia/secrets

# Gerar senha forte para Redis (32 caracteres)
openssl rand -base64 32 > backend-hormonia/secrets/redis_password.txt

# Proteger arquivo
chmod 600 backend-hormonia/secrets/redis_password.txt

# Adicionar ao .gitignore
echo "secrets/" >> backend-hormonia/.gitignore
```

#### 2.2. Criar Configuração Redis

```bash
# Criar diretório de configuração
mkdir -p backend-hormonia/config

# Copiar configuração Redis
cp docs/backend/docker-fixes/redis.conf backend-hormonia/config/redis.conf

# Atualizar com senha do arquivo secrets
REDIS_PASSWORD=$(cat backend-hormonia/secrets/redis_password.txt)
sed -i "s/\${REDIS_PASSWORD}/$REDIS_PASSWORD/g" backend-hormonia/config/redis.conf
```

#### 2.3. Implementar Docker Compose Seguro

```bash
# Copiar docker-compose corrigido
cp docs/backend/docker-fixes/docker-compose.yml.fixed backend-hormonia/docker-compose.yml

# Copiar template de environment
cp docs/backend/docker-fixes/.env.docker.example backend-hormonia/.env.docker

# Configurar variáveis de ambiente
cd backend-hormonia
cp .env.docker .env

# IMPORTANTE: Editar .env com valores de produção
nano .env
# Atualizar:
# - REDIS_PASSWORD (usar valor de secrets/redis_password.txt)
# - FLOWER_USER e FLOWER_PASSWORD
# - Todas as outras credenciais
```

#### 2.4. Configurar Autenticação no Flower

No arquivo `.env`, adicionar:

```bash
FLOWER_USER=admin
FLOWER_PASSWORD=$(openssl rand -base64 24)
```

#### 2.5. Testar Configuração de Segurança

```bash
# Iniciar serviços
docker-compose up -d

# Verificar logs
docker-compose logs -f

# Testar acesso ao Redis (deve exigir senha)
docker exec -it hormonia-redis redis-cli
# > AUTH <senha_do_arquivo_secrets>
# > PING
# > PONG

# Testar Flower (deve exigir autenticação)
curl http://localhost:5555/flower
# Deve retornar 401 Unauthorized

# Testar com autenticação
curl -u admin:$FLOWER_PASSWORD http://localhost:5555/flower/api/workers
```

---

### Fase 3: Otimizações (1-2 dias)

#### 3.1. Implementar .dockerignore Otimizado

```bash
# Copiar .dockerignore corrigido
cp docs/backend/docker-fixes/.dockerignore.fixed backend-hormonia/.dockerignore

# Rebuild e comparar tamanho de contexto
docker build --no-cache -t hormonia-backend:optimized .
```

#### 3.2. Adicionar Resource Limits

O `docker-compose.yml.fixed` já inclui resource limits. Ajustar conforme recursos disponíveis:

```yaml
# Para servidores com mais RAM, ajustar em docker-compose.yml:
deploy:
  resources:
    limits:
      cpus: '2.0'      # Era 1.0
      memory: 2G       # Era 1G
    reservations:
      cpus: '1.0'      # Era 0.5
      memory: 1G       # Era 512M
```

#### 3.3. Implementar BuildKit Cache Mounts

```bash
# Habilitar BuildKit
export DOCKER_BUILDKIT=1

# Rebuild com cache mounts
docker build -t hormonia-backend:cached .

# Comparar tempo de build
time docker build --no-cache -t hormonia-backend:no-cache .
time docker build -t hormonia-backend:cached .
# Esperado: ~50% mais rápido em rebuilds
```

#### 3.4. Configurar Networks Segregadas

O `docker-compose.yml.fixed` já inclui networks segregadas. Verificar:

```bash
# Listar networks criadas
docker network ls | grep hormonia

# Inspecionar network cache-network (deve ser internal)
docker network inspect backend-hormonia_cache-network
# "Internal": true
```

---

### Fase 4: Validação e Testes (1 dia)

#### 4.1. Testes de Integração

```bash
# Subir todos os serviços
docker-compose up -d

# Aguardar todos os serviços ficarem healthy
docker-compose ps

# Testar healthchecks
for service in redis celery-worker celery-beat celery-flower; do
  echo "Testing $service..."
  docker inspect backend-hormonia_${service} | grep -A 5 Health
done

# Testar comunicação entre serviços
docker-compose exec celery-worker celery -A app.celery_app inspect ping
```

#### 4.2. Testes de Performance

```bash
# Benchmark de Redis
docker-compose exec redis redis-benchmark -a $(cat secrets/redis_password.txt) -n 100000 -q

# Verificar uso de recursos
docker stats backend-hormonia_celery-worker_1 backend-hormonia_redis_1
```

#### 4.3. Testes de Segurança

```bash
# Verificar que Redis não está exposto externamente
docker port hormonia-redis
# Não deve listar portas públicas

# Verificar que Flower requer autenticação
curl -v http://localhost:5555/flower
# Deve retornar 401

# Verificar que comandos perigosos estão desabilitados
docker-compose exec redis redis-cli -a $(cat secrets/redis_password.txt)
# > FLUSHALL
# Deve retornar erro
```

#### 4.4. Testes de Resiliência

```bash
# Testar restart automático
docker-compose stop celery-worker
sleep 5
docker-compose ps
# celery-worker deve estar "Up" novamente (restart policy)

# Testar limite de memória
docker-compose exec celery-worker python -c "
import numpy as np
try:
    # Tentar alocar 2GB (acima do limite de 1GB)
    big_array = np.zeros((1024, 1024, 256))
except MemoryError:
    print('Memory limit working!')
"
```

---

## 🚀 Deploy em Produção

### Railway

```bash
# Commit das mudanças
git add .
git commit -m "feat(docker): Implement multi-stage build, security improvements, and resource limits

- Multi-stage build reduces image size by ~60%
- Healthcheck uses wget for reliability
- Docker secrets for Redis password
- Network segregation for security
- Resource limits prevent resource exhaustion
- Flower authentication enabled
- Python 3.13 compatibility across all Dockerfiles"

# Push para branch
git push origin feat/docker-improvements

# Criar Pull Request
gh pr create --title "Docker improvements: security, performance, and reliability" \
  --body "Implements all critical and high-priority fixes from Docker review report"

# Após aprovação, merge e deploy
git checkout main
git merge feat/docker-improvements
git push origin main
```

Railway detectará automaticamente o novo `Dockerfile` e iniciará o deploy.

### Render/Fly.io

```bash
# Adicionar arquivo de configuração específico
# render.yaml ou fly.toml conforme plataforma

# Fazer deploy
fly deploy  # ou render deploy
```

---

## 📊 Checklist de Validação

### Antes do Deploy

- [ ] Todos os testes passando localmente
- [ ] Imagem Docker build sem erros
- [ ] Healthcheck funcionando (status "healthy")
- [ ] Todos os serviços iniciam corretamente
- [ ] Logs sem erros críticos
- [ ] Resource limits configurados
- [ ] Secrets não estão no código (gitignored)
- [ ] .env.example atualizado com novas variáveis
- [ ] Documentação atualizada

### Após Deploy em Staging

- [ ] API responde corretamente
- [ ] Celery workers processando tarefas
- [ ] Flower dashboard acessível com autenticação
- [ ] Redis funcionando com persistência
- [ ] Healthchecks reportando status correto
- [ ] Métricas de performance dentro do esperado
- [ ] Logs estruturados e sem erros

### Após Deploy em Produção

- [ ] Zero downtime durante deploy
- [ ] Todos os endpoints funcionando
- [ ] Background jobs executando
- [ ] Monitoramento ativo
- [ ] Alertas configurados
- [ ] Backup funcionando
- [ ] Rollback plan testado

---

## 🔧 Troubleshooting

### Problema: Build falha com "No space left on device"

```bash
# Limpar imagens não utilizadas
docker system prune -a --volumes

# Verificar espaço
docker system df
```

### Problema: Healthcheck sempre failing

```bash
# Verificar logs do container
docker logs hormonia-backend

# Testar healthcheck manualmente
docker exec hormonia-backend wget --spider http://localhost:8000/health

# Aumentar start-period se necessário
# No Dockerfile: --start-period=120s
```

### Problema: Celery workers não conectam ao Redis

```bash
# Verificar que REDIS_PASSWORD está correto
docker-compose exec celery-worker env | grep REDIS

# Verificar conectividade
docker-compose exec celery-worker ping redis

# Verificar logs do Redis
docker-compose logs redis
```

### Problema: Flower não exige autenticação

```bash
# Verificar variáveis de ambiente
docker-compose exec celery-flower env | grep FLOWER

# Verificar comando do Flower
docker-compose exec celery-flower ps aux | grep flower
```

---

## 📚 Recursos Adicionais

- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [FastAPI Docker Deployment](https://fastapi.tiangolo.com/deployment/docker/)
- [Python 3.13 Release Notes](https://docs.python.org/3.13/whatsnew/3.13.html)
- [Railway Docker Documentation](https://docs.railway.app/deploy/dockerfiles)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)

---

## 🎯 Próximos Passos

1. Implementar monitoramento com Prometheus + Grafana
2. Configurar alertas no Sentry
3. Implementar CI/CD com GitHub Actions
4. Adicionar testes de carga (Locust/k6)
5. Configurar backup automático do Redis
6. Implementar Redis Sentinel para high availability

---

**Última atualização:** 2025-10-05
**Versão:** 1.0.0
