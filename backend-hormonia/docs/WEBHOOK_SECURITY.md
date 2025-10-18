# Webhook Security Guide

## 📋 Visão Geral

Este documento descreve as medidas de segurança implementadas para webhooks no sistema Hormonia, incluindo validação HMAC, prevenção de replay attacks e idempotência.

**CRITICAL FIX #3**: Implementação completa de segurança de webhooks para prevenir ataques.

## 🎯 Ameaças e Mitigações

### Ameaças Identificadas

| Ameaça | Descrição | Impacto | Mitigação |
|--------|-----------|---------|-----------|
| **Tampering** | Modificação do payload do webhook | Alto | HMAC-SHA256 signature |
| **Replay Attacks** | Reenvio de webhooks válidos | Alto | Timestamp validation |
| **Duplicate Processing** | Processamento múltiplo do mesmo evento | Médio | Idempotency keys |
| **Unauthorized Access** | Webhooks de fontes não autorizadas | Crítico | Secret key validation |
| **Timing Attacks** | Descoberta de secrets via timing | Médio | Constant-time comparison |

## 🔒 Camadas de Segurança

### Camada 1: HMAC Signature Verification

**O que é**: HMAC (Hash-based Message Authentication Code) usando SHA-256.

**Como funciona**:
1. Evolution API calcula hash do payload usando secret compartilhado
2. Hash é enviado no header `X-Webhook-Signature`
3. Backend recalcula hash e compara
4. Se hashes não correspondem, request é rejeitado

**Implementação**:

```python
# Backend calcula expected signature
expected_signature = hmac.new(
    WEBHOOK_SECRET.encode('utf-8'),
    payload_bytes,
    hashlib.sha256
).hexdigest()

# Compara com signature recebida (constant-time)
if not hmac.compare_digest(received_signature, expected_signature):
    raise HTTPException(status_code=401, detail="Invalid signature")
```

**Configuração**:

```bash
# .env
EVOLUTION_WEBHOOK_SECRET=your-strong-secret-key-here-min-32-chars
```

**Geração de Secret Seguro**:

```bash
# Gerar secret de 64 caracteres
openssl rand -hex 32

# Ou usar Python
python -c "import secrets; print(secrets.token_hex(32))"
```

### Camada 2: Timestamp Validation

**O que é**: Validação da idade do webhook para prevenir replay attacks.

**Como funciona**:
1. Evolution API envia timestamp Unix no header `X-Webhook-Timestamp`
2. Backend verifica se timestamp está dentro da janela permitida (5 minutos)
3. Webhooks expirados são rejeitados

**Implementação**:

```python
MAX_TIMESTAMP_AGE_SECONDS = 300  # 5 minutes

webhook_time = int(x_webhook_timestamp)
current_time = int(time.time())
time_diff = abs(current_time - webhook_time)

if time_diff > MAX_TIMESTAMP_AGE_SECONDS:
    raise HTTPException(
        status_code=401,
        detail="Webhook timestamp expired"
    )
```

**Por que 5 minutos?**:
- Suficiente para atrasos de rede normais
- Pequeno o bastante para limitar janela de replay
- Compatível com NTP drift típico

**Signature com Timestamp** (Recomendado):

```python
# Incluir timestamp na signature para segurança adicional
signature_payload = f"{timestamp}.{payload}"
signature = hmac.new(secret, signature_payload.encode(), hashlib.sha256).hexdigest()
```

### Camada 3: Idempotency

**O que é**: Prevenção de processamento duplicado do mesmo webhook.

**Como funciona**:
1. Evolution API envia ID único no header `X-Webhook-Id`
2. Backend verifica se ID já foi processado nas últimas 24 horas
3. Webhooks duplicados retornam sucesso mas não são reprocessados

**Implementação**:

```python
# Verificar se webhook_id já existe
existing = db.execute(
    select(WebhookEvent).where(
        WebhookEvent.webhook_id == webhook_id,
        WebhookEvent.created_at >= cutoff_time
    )
).first()

if existing:
    return {"status": "duplicate", "message": "Already processed"}
```

**Janela de Idempotência**: 24 horas
- Cobre reenvios típicos de retry
- Limite de armazenamento razoável
- Cleanup automático de IDs antigos

## 🔧 Configuração

### 1. Variáveis de Ambiente

```bash
# Required
EVOLUTION_WEBHOOK_SECRET=your-strong-secret-key-here

# Optional (with defaults)
ENVIRONMENT=production  # production, staging, development
WEBHOOK_TIMESTAMP_MAX_AGE=300  # seconds
WEBHOOK_IDEMPOTENCY_WINDOW=24  # hours
```

### 2. Evolution API Configuration

Configure webhooks na Evolution API:

```bash
# Webhook URL
https://api.hormonia.com/webhooks/evolution/message

# Headers esperados
X-Webhook-Signature: <hmac-sha256-hex>
X-Webhook-Timestamp: <unix-timestamp>
X-Webhook-Id: <unique-uuid>
```

### 3. Testes de Segurança

```bash
# Testar signature validation
curl -X POST https://api.hormonia.com/webhooks/evolution/message \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: invalid" \
  -d '{"event": "test"}'
# Expected: 401 Unauthorized

# Testar timestamp validation
curl -X POST https://api.hormonia.com/webhooks/evolution/message \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: <valid-signature>" \
  -H "X-Webhook-Timestamp: 1000000000" \
  -d '{"event": "test"}'
# Expected: 401 Unauthorized (timestamp expired)
```

## 🚨 Melhores Práticas

### ✅ SEMPRE FAÇA

1. **Use Secrets Fortes**
   ```bash
   # Mínimo 32 caracteres, preferível 64
   # Use gerador criptográfico
   EVOLUTION_WEBHOOK_SECRET=$(openssl rand -hex 32)
   ```

2. **Rotacione Secrets Regularmente**
   ```bash
   # Suporte para múltiplos secrets durante rotação
   EVOLUTION_WEBHOOK_SECRET=new-secret
   EVOLUTION_WEBHOOK_SECRET_OLD=old-secret  # Aceitar por 7 dias
   ```

3. **Monitore Falhas de Autenticação**
   ```python
   # Alerte em taxa alta de 401s
   if failed_auth_rate > 10:  # 10 falhas por minuto
       alert_security_team("High rate of webhook auth failures")
   ```

4. **Use HTTPS Sempre**
   - NUNCA aceite webhooks em HTTP
   - Enforce TLS 1.2 ou superior
   - Use certificados válidos

5. **Implemente Rate Limiting**
   ```python
   # Limite de webhooks por origem
   @limiter.limit("100/minute")
   async def webhook_endpoint():
       pass
   ```

### ❌ NUNCA FAÇA

1. **Nunca Logue Secrets**
   ```python
   # ❌ ERRADO
   logger.info(f"Webhook secret: {settings.WEBHOOK_SECRET}")
   
   # ✅ CORRETO
   logger.info("Webhook secret configured: ✓")
   ```

2. **Nunca Aceite Webhooks Sem Signature em Produção**
   ```python
   # ❌ ERRADO
   if not settings.WEBHOOK_SECRET:
       return  # Processar mesmo sem validação
   
   # ✅ CORRETO
   if not settings.WEBHOOK_SECRET:
       if settings.ENVIRONMENT == "production":
           raise HTTPException(401, "Webhook auth not configured")
   ```

3. **Nunca Use String Comparison Simples**
   ```python
   # ❌ ERRADO (vulnerável a timing attacks)
   if received_signature == expected_signature:
       pass
   
   # ✅ CORRETO
   if hmac.compare_digest(received_signature, expected_signature):
       pass
   ```

4. **Nunca Ignore Erros de Validação**
   ```python
   # ❌ ERRADO
   try:
       validate_signature()
   except Exception:
       pass  # Processar mesmo com erro
   
   # ✅ CORRETO
   try:
       validate_signature()
   except Exception as e:
       logger.error(f"Validation failed: {e}")
       raise HTTPException(401)
   ```

## 📊 Monitoramento

### Métricas Importantes

```python
# Prometheus metrics
webhook_requests_total = Counter('webhook_requests_total', 'Total webhook requests', ['endpoint', 'status'])
webhook_validation_failures = Counter('webhook_validation_failures', 'Webhook validation failures', ['reason'])
webhook_processing_duration = Histogram('webhook_processing_duration', 'Webhook processing time')
webhook_duplicate_count = Counter('webhook_duplicate_count', 'Duplicate webhook attempts')
```

### Alertas Recomendados

1. **Taxa de Falha de Autenticação Alta**
   - Threshold: > 10 falhas/minuto
   - Pode indicar ataque ou misconfiguration

2. **Webhooks Expirados (Timestamp)**
   - Threshold: > 5% dos webhooks
   - Pode indicar clock skew ou ataque

3. **Taxa de Duplicatas Alta**
   - Threshold: > 20% dos webhooks
   - Pode indicar problema no sender ou retry excessivo

4. **Secret Não Configurado em Produção**
   - Severity: CRITICAL
   - Block deployment

### Dashboard de Segurança

```python
# Queries úteis para dashboard

# Taxa de sucesso de webhooks
SELECT 
    COUNT(*) FILTER (WHERE status = 'success') * 100.0 / COUNT(*) as success_rate
FROM webhook_events
WHERE created_at > NOW() - INTERVAL '1 hour';

# Top razões de falha
SELECT 
    failure_reason,
    COUNT(*) as count
FROM webhook_events
WHERE status = 'failed'
    AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY failure_reason
ORDER BY count DESC;

# Detecção de replay attacks
SELECT 
    webhook_id,
    COUNT(*) as attempt_count,
    MIN(created_at) as first_attempt,
    MAX(created_at) as last_attempt
FROM webhook_events
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY webhook_id
HAVING COUNT(*) > 1;
```

## 🔍 Troubleshooting

### Problema: "Invalid webhook signature"

**Causas**:
1. Secret key diferente entre sender e receiver
2. Payload modificado (body parsing alterou conteúdo)
3. Charset/encoding diferente

**Solução**:
```bash
# Verificar secret configurado
echo $EVOLUTION_WEBHOOK_SECRET | wc -c  # Deve ser >= 32

# Testar localmente com secret conhecido
python scripts/test_webhook_signature.py

# Verificar logs do Evolution API
curl https://evolution-api.com/logs
```

### Problema: "Webhook timestamp expired"

**Causas**:
1. Clock skew entre servidor e Evolution API
2. Webhook atrasado (retry muito tarde)
3. Timezone incorreta

**Solução**:
```bash
# Verificar clock do servidor (deve usar NTP)
timedatectl status

# Sincronizar clock
sudo ntpdate -s time.nist.gov

# Verificar timezone
date -u  # Deve ser UTC

# Ajustar MAX_TIMESTAMP_AGE se necessário
export WEBHOOK_TIMESTAMP_MAX_AGE=600  # 10 minutos
```

### Problema: "Webhook already processed (duplicate)"

**Causas**:
1. Retry legítimo do Evolution API
2. Múltiplos workers processando simultaneamente
3. Race condition na verificação de idempotência

**Solução**:
```bash
# Verificar logs de processsamento
grep "webhook_id=<id>" logs/app.log

# Verificar se webhook foi processado com sucesso
psql $DATABASE_URL -c "SELECT * FROM webhook_events WHERE webhook_id = '<id>'"

# Se false positive, limpar cache
redis-cli DEL webhook:idempotency:<id>
```

### Problema: "Webhook authentication not configured"

**Causas**:
1. EVOLUTION_WEBHOOK_SECRET não definido
2. Variável de ambiente não carregada
3. Secret vazio ou nulo

**Solução**:
```bash
# Verificar variável definida
env | grep EVOLUTION_WEBHOOK_SECRET

# Gerar novo secret
export EVOLUTION_WEBHOOK_SECRET=$(openssl rand -hex 32)

# Atualizar em Railway/Vercel
railway variables set EVOLUTION_WEBHOOK_SECRET="<secret>"

# Reiniciar aplicação
railway up
```

## 🧪 Testes

### Teste Manual de Webhook

```bash
# Script de teste completo
#!/bin/bash

WEBHOOK_URL="https://api.hormonia.com/webhooks/evolution/message"
SECRET="your-secret-here"
PAYLOAD='{"event":"messages.upsert","data":{"key":"test"}}'
TIMESTAMP=$(date +%s)

# Calcular signature
SIGNATURE=$(echo -n "${TIMESTAMP}.${PAYLOAD}" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

# Enviar webhook
curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: $SIGNATURE" \
  -H "X-Webhook-Timestamp: $TIMESTAMP" \
  -H "X-Webhook-Id: $(uuidgen)" \
  -d "$PAYLOAD"
```

### Testes Automatizados

```python
# tests/test_webhook_security.py

import pytest
import hmac
import hashlib
import time
from fastapi.testclient import TestClient

def test_webhook_signature_valid(client: TestClient):
    """Test webhook with valid signature is accepted."""
    payload = b'{"event": "test"}'
    timestamp = str(int(time.time()))
    
    signature = hmac.new(
        SECRET.encode(),
        f"{timestamp}.{payload.decode()}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    response = client.post(
        "/webhooks/evolution/message",
        content=payload,
        headers={
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Id": "test-id-1"
        }
    )
    
    assert response.status_code == 200

def test_webhook_signature_invalid(client: TestClient):
    """Test webhook with invalid signature is rejected."""
    response = client.post(
        "/webhooks/evolution/message",
        json={"event": "test"},
        headers={"X-Webhook-Signature": "invalid"}
    )
    
    assert response.status_code == 401
    assert "Invalid signature" in response.json()["detail"]

def test_webhook_timestamp_expired(client: TestClient):
    """Test webhook with expired timestamp is rejected."""
    payload = b'{"event": "test"}'
    old_timestamp = str(int(time.time()) - 400)  # 6 minutes ago
    
    signature = hmac.new(
        SECRET.encode(),
        f"{old_timestamp}.{payload.decode()}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    response = client.post(
        "/webhooks/evolution/message",
        content=payload,
        headers={
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": old_timestamp
        }
    )
    
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()

def test_webhook_idempotency(client: TestClient):
    """Test duplicate webhook is detected."""
    payload = b'{"event": "test"}'
    timestamp = str(int(time.time()))
    webhook_id = "duplicate-test-id"
    
    signature = hmac.new(
        SECRET.encode(),
        f"{timestamp}.{payload.decode()}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "X-Webhook-Signature": signature,
        "X-Webhook-Timestamp": timestamp,
        "X-Webhook-Id": webhook_id
    }
    
    # First request
    response1 = client.post(
        "/webhooks/evolution/message",
        content=payload,
        headers=headers
    )
    assert response1.status_code == 200
    
    # Duplicate request
    response2 = client.post(
        "/webhooks/evolution/message",
        content=payload,
        headers=headers
    )
    assert response2.status_code == 200
    assert response2.json()["status"] == "duplicate"
```

## 📚 Recursos Adicionais

- [OWASP Webhook Security](https://cheatsheetseries.owasp.org/cheatsheets/Webhook_Security_Cheat_Sheet.html)
- [HMAC Specification (RFC 2104)](https://tools.ietf.org/html/rfc2104)
- [Timing Attack Prevention](https://codahale.com/a-lesson-in-timing-attacks/)
- [Evolution API Documentation](https://doc.evolution-api.com/)

## 🆘 Suporte

Se encontrar problemas de segurança:

1. **Não abra issue público** (pode expor vulnerabilidade)
2. **Envie email para**: security@hormonia.com
3. **Use**: security@hormonia.com PGP key para comunicação sensível
4. **Aguarde**: resposta em 24-48 horas

---

**Última Atualização**: Janeiro 2024  
**Versão**: 1.0  
**Autor**: Sistema Hormonia - Security Team