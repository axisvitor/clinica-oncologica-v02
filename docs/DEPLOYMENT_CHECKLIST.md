# Checklist de Deployment - Correções API v2

## 📋 Pré-requisitos

- [ ] Python 3.11+
- [ ] PostgreSQL 15+
- [ ] Redis 7+
- [ ] Alembic migrations atualizadas

---

## 🔧 Validação Local

### 1. Verificar Dependências
```bash
cd backend-hormonia
pip install -r requirements.txt
```

### 2. Rodar Testes
```bash
# Testes unitários
pytest tests/ -v

# Testes de integração v2
pytest tests/integration/test_v2_endpoints.py -v --cov=app.api.v2

# Health checks
pytest tests/integration/test_health.py -v
```

### 3. Validar Schemas
```bash
# Gerar schema OpenAPI
python -c "from app.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > openapi.json

# Validar tipos UUID
curl http://localhost:8000/api/v2/patients | jq '.data[0].id' | grep -E '^"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"$'
```

### 4. Testar Cache
```bash
# Limpar cache
redis-cli FLUSHDB

# Request 1 (cache miss)
time curl http://localhost:8000/api/v2/analytics/overview

# Request 2 (cache hit - deve ser ~10x mais rápido)
time curl http://localhost:8000/api/v2/analytics/overview

# Verificar chaves
redis-cli KEYS "analytics:v2:*"
```

### 5. Testar Rate Limiting
```bash
# Criar paciente (limite: 20/hora)
for i in {1..25}; do
  curl -X POST http://localhost:8000/api/v2/patients \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name": "Test '$i'", "email": "test'$i'@example.com", "phone": "11999999999", "doctor_id": "uuid"}' \
    -w "%{http_code}\n" -o /dev/null -s
done
# Espera-se: 20x 201, 5x 429
```

### 6. Testar RBAC
```bash
# Token de usuário normal (deve retornar 403)
curl -X POST http://localhost:8000/api/v2/patients \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "email": "test@example.com", "phone": "11999999999", "doctor_id": "uuid"}' \
  -w "%{http_code}\n"

# Token de DOCTOR/ADMIN (deve retornar 201)
curl -X POST http://localhost:8000/api/v2/patients \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "email": "test@example.com", "phone": "11999999999", "doctor_id": "uuid"}' \
  -w "%{http_code}\n"
```

---

## 🚀 Deployment Staging

### 1. Backup
```bash
# PostgreSQL
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME > backup_$(date +%Y%m%d_%H%M%S).sql

# Redis (opcional)
redis-cli SAVE
```

### 2. Deploy
```bash
# Build image
docker build -t hormonia-backend:2.0.0 .

# Deploy via Railway/Docker
railway up
# ou
docker-compose up -d
```

### 3. Health Checks
```bash
# Liveness
curl https://staging.hormonia.com/health/live

# Readiness (deve retornar dependências)
curl https://staging.hormonia.com/health/ready | jq '.dependencies'

# Metrics
curl https://staging.hormonia.com/health/metrics | jq '.process.memory'
```

### 4. Smoke Tests
```bash
# API v2 Health
curl https://staging.hormonia.com/api/v2/health

# Listar pacientes (paginação)
curl https://staging.hormonia.com/api/v2/patients?limit=10 | jq '.has_more'

# Analytics (cache)
curl https://staging.hormonia.com/api/v2/analytics/overview \
  -H "Authorization: Bearer $DOCTOR_TOKEN" | jq '.completion_rate'
```

---

## 📊 Monitoramento

### Métricas-chave
```bash
# Prometheus
curl https://staging.hormonia.com/metrics | grep http_request_duration

# Performance
curl https://staging.hormonia.com/health/performance | jq '.requests.avg_duration_ms'

# Cache hit rate
redis-cli INFO stats | grep keyspace_hits
```

### Logs
```bash
# Railway
railway logs --tail 100

# Docker
docker logs hormonia-backend --tail 100 -f | grep -E "(ERROR|WARNING|rate_limit)"
```

### Alertas
- [ ] Taxa de erro > 1%
- [ ] Latência p95 > 500ms
- [ ] Cache hit rate < 70%
- [ ] Rate limit hits > 100/min

---

## 🔄 Rollback Plan

### Se houver problemas:

1. **Reverter Deploy**
```bash
railway rollback
# ou
docker-compose down && docker-compose up -d --build <previous_tag>
```

2. **Restaurar DB** (se necessário)
```bash
psql -h $DB_HOST -U $DB_USER -d $DB_NAME < backup_YYYYMMDD_HHMMSS.sql
```

3. **Limpar Cache**
```bash
redis-cli FLUSHDB
```

---

## ✅ Validação Pós-Deploy

### Checklist de Produção

- [ ] Health checks retornando 200
- [ ] Endpoints v2 respondendo corretamente
- [ ] Cache funcionando (verificar Redis)
- [ ] Rate limiting ativo
- [ ] RBAC rejeitando acessos não autorizados
- [ ] Logs sem erros críticos
- [ ] Métricas Prometheus sendo coletadas
- [ ] Alertas configurados
- [ ] Frontend conectado à API v2
- [ ] Testes E2E passando

---

## 🐛 Troubleshooting

### Cache não funciona
```bash
# Verificar Redis
redis-cli PING
redis-cli INFO | grep connected_clients

# Testar manualmente
redis-cli SET test_key "test_value" EX 60
redis-cli GET test_key
```

### Rate limit não ativando
```bash
# Verificar se slowapi está instalado
pip show slowapi

# Verificar logs
grep -i "rate.limit" logs/*.log
```

### RBAC permitindo acesso incorreto
```bash
# Verificar token
curl https://staging.hormonia.com/api/v2/patients \
  -H "Authorization: Bearer $TOKEN" -v 2>&1 | grep "X-User-Role"

# Logs de autenticação
grep "get_doctor_user" logs/*.log
```

### Paginação retornando duplicatas
```bash
# Validar cursor
curl "https://staging.hormonia.com/api/v2/patients?limit=10" | jq '.next_cursor' | base64 -d

# Verificar ordenação
curl "https://staging.hormonia.com/api/v2/patients?limit=10" | jq '.data[].created_at'
```

---

## 📞 Contatos

- **Backend Lead**: [Nome]
- **DevOps**: [Nome]
- **On-call**: [Link Pagerduty/Slack]

---

## 📚 Referências

- [ENDPOINT_REVIEW_REPORT.md](./ENDPOINT_REVIEW_REPORT.md) - Relatório completo
- [SPRINT_4_KICKOFF.md](./SPRINT_4_KICKOFF.md) - Contexto do sprint
- [API_V2_GUIDE.md](./SPRINT_4_API_V2_GUIDE.md) - Guia da API v2

---

**Última atualização**: 17 de Outubro de 2025  
**Versão**: 2.0.0
