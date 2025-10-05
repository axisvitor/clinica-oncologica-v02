# 🔧 Guia de Correção Redis - Railway Dashboard

## ⚠️ ATENÇÃO: Aplique estas correções EXATAMENTE como indicado

### 📋 Pré-requisitos
- Acesso ao Railway Dashboard
- Projeto: clinica-oncologica-v02
- Serviço: backend-hormonia

---

## 🔴 CORREÇÃO 1: REDIS_URL (CRÍTICO)

### ❌ Configuração Atual (ERRADA):
```
rediss://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/ssl_cert_reqs=none
```

### ✅ Configuração Correta:
```
rediss://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149?ssl_cert_reqs=none
```

### 🎯 O que mudou:
- **Antes**: `/ssl_cert_reqs=none` (tratado como database number)
- **Depois**: `?ssl_cert_reqs=none` (query parameter correto)

### 📝 Passos no Railway:
1. Railway Dashboard → Projeto → backend-hormonia → Variables
2. Localizar variável `REDIS_URL`
3. Substituir `/` por `?` antes de `ssl_cert_reqs=none`
4. Salvar (Railway redeploya automaticamente)

---

## 🔴 CORREÇÃO 2: CELERY_BROKER_URL (CRÍTICO)

### ❌ Configuração Atual (ERRADA):
```
redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
```

### ✅ Configuração Correta:
```
rediss://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0?ssl_cert_reqs=none
```

### 🎯 O que mudou:
- **Protocolo**: `redis://` → `rediss://` (adicionar SSL)
- **Parâmetro SSL**: Adicionar `?ssl_cert_reqs=none` ao final

### 📝 Passos no Railway:
1. Railway Dashboard → Projeto → backend-hormonia → Variables
2. Localizar variável `CELERY_BROKER_URL`
3. Substituir valor completo pela versão correta acima
4. Salvar

---

## 🔴 CORREÇÃO 3: CELERY_RESULT_BACKEND (CRÍTICO)

### ❌ Configuração Atual (ERRADA):
```
redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
```

### ✅ Configuração Correta:
```
rediss://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0?ssl_cert_reqs=none
```

### 🎯 O que mudou:
- Idêntico à correção do CELERY_BROKER_URL

### 📝 Passos no Railway:
1. Railway Dashboard → Projeto → backend-hormonia → Variables
2. Localizar variável `CELERY_RESULT_BACKEND`
3. Substituir valor completo pela versão correta acima
4. Salvar

---

## ✅ VALIDAÇÃO PÓS-CORREÇÃO

### 1️⃣ Aguardar Redeploy Automático
- Railway redeploya automaticamente após salvar variáveis
- Aguardar ~2-3 minutos

### 2️⃣ Verificar Logs do Backend
Acessar: Railway → backend-hormonia → Deployments → Logs

**Buscar por estas mensagens de SUCESSO:**
```
✅ Redis connection established
✅ WebSocket events enabled
✅ Celery worker connected to broker
```

**NÃO deve aparecer:**
```
❌ ERROR - [SSL] record layer failure
❌ WARNING - Continuing without WebSocket events
```

### 3️⃣ Testar Endpoint de Health
```bash
curl https://clinica-oncologica-production.up.railway.app/health
```

**Resposta esperada:**
```json
{
  "status": "healthy",
  "redis": "connected",
  "websocket": "enabled",
  "celery": "connected"
}
```

---

## 🎯 IMPACTO ESPERADO

### Antes das Correções:
- ❌ Redis principal: SSL handshake failure
- ❌ WebSocket events: Desabilitado
- ❌ Real-time features: Indisponíveis
- ❌ Celery tasks: Broker não conecta
- ⚠️ Rate limiting: Local apenas (não distribuído)
- ⚠️ Session cache: Sem compartilhamento entre instâncias

### Depois das Correções:
- ✅ Redis principal: Conectado com SSL
- ✅ WebSocket events: Habilitado
- ✅ Real-time features: Funcionando
- ✅ Celery tasks: Worker conectado e processando
- ✅ Rate limiting: Distribuído entre todas instâncias
- ✅ Session cache: Compartilhado corretamente

---

## 🔍 TROUBLESHOOTING

### Se Redis continuar falhando após correções:

1. **Verificar senha no Railway:**
   ```bash
   # A senha deve ser EXATAMENTE:
   6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR
   ```

2. **Verificar host Redis Cloud:**
   ```bash
   redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
   ```

3. **Testar conexão manual:**
   ```bash
   redis-cli -h redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com \
             -p 14149 \
             -a 6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR \
             --tls \
             --insecure \
             PING
   # Deve retornar: PONG
   ```

4. **Verificar Python 3.13 SSL:**
   - Python 3.13 tem validação SSL mais estrita
   - `ssl_cert_reqs=none` é OBRIGATÓRIO para Redis Cloud

---

## 📊 CHECKLIST DE VALIDAÇÃO

Marque após aplicar cada correção:

- [ ] REDIS_URL: `/` substituído por `?`
- [ ] CELERY_BROKER_URL: `redis://` → `rediss://` + `?ssl_cert_reqs=none`
- [ ] CELERY_RESULT_BACKEND: `redis://` → `rediss://` + `?ssl_cert_reqs=none`
- [ ] Railway redeploy concluído
- [ ] Logs backend: "Redis connection established"
- [ ] Logs backend: "WebSocket events enabled"
- [ ] Logs backend: "Celery worker connected"
- [ ] Endpoint /health retorna status "healthy"
- [ ] Sem erros SSL nos logs

---

## 📞 PRÓXIMOS PASSOS

Após aplicar as correções e validar:

1. **Monitorar por 24h**: Verificar estabilidade da conexão Redis
2. **Testar features real-time**: WebSocket, notificações, updates automáticos
3. **Verificar Celery tasks**: Confirmar processamento assíncrono funcionando
4. **Fase 2 (opcional)**: Refatoração de código para consolidar implementações Redis

---

**Preparado por**: Hive-Mind Collective Intelligence System
**Data**: 2025-10-05
**Baseado em**: REDIS_AUDIT_COMPLETE_REPORT.md
