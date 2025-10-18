# Idempotency Guide - Message Sending

## 📋 Visão Geral

Este documento descreve a implementação de idempotência no sistema de envio de mensagens do Hormonia.

**CRITICAL FIX #5**: Implementação de idempotência para prevenir envio duplicado de mensagens WhatsApp.

## 🎯 Por que Idempotência?

### Problemas sem Idempotência:
- ❌ Mensagens duplicadas enviadas ao paciente
- ❌ Custos desnecessários (cada mensagem tem custo)
- ❌ Má experiência do usuário (spam)
- ❌ Dificuldade de debugging
- ❌ Retries causam duplicatas

### Benefícios com Idempotência:
- ✅ Mensagem enviada exatamente uma vez
- ✅ Retries seguros (mesmo com falhas)
- ✅ Proteção contra race conditions
- ✅ Melhor experiência do usuário
- ✅ Redução de custos

## 🔧 Como Funciona

### Arquitetura de 3 Camadas

```
┌─────────────────────────────────────────────────────────┐
│  1. IDEMPOTENCY KEY GENERATION                          │
│     Generate or accept unique key per message intent    │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  2. REDIS CACHE (Fast Path)                             │
│     Check if message already sent (TTL: 24h)            │
│     ├── HIT  → Return existing message ✅               │
│     └── MISS → Continue to database check               │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  3. DATABASE CHECK (Persistent)                         │
│     Check unique constraint (patient_id, idempotency_key)│
│     ├── EXISTS → Return existing message ✅             │
│     └── NEW    → Send message                           │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  4. SEND MESSAGE                                        │
│     Send via Evolution API + Store in DB + Cache result │
└─────────────────────────────────────────────────────────┘
```

## 💡 Idempotency Key

### Geração Automática

A chave de idempotência é gerada automaticamente baseada em:
- **Patient ID**: Destinatário único
- **Content**: Conteúdo da mensagem
- **Message Type**: Tipo de mensagem
- **Timestamp**: Timestamp (arredondado para minuto)

```python
# Exemplo de geração
components = f"{patient_id}:{content}:{message_type}:{timestamp_minute}"
hash_digest = hashlib.sha256(components.encode("utf-8")).hexdigest()
idempotency_key = f"msg_{hash_digest[:32]}"

# Exemplo de resultado
# msg_a1b2c3d4e5f6789012345678901234
```

### Por que Incluir Timestamp?

- **Permite reenvios legítimos**: Se enviar a mesma mensagem após 1 minuto, é considerado novo envio
- **Evita colisões**: Mensagens idênticas em momentos diferentes são distintas
- **Tolerância razoável**: Janela de 1 minuto permite retries rápidos

### Chave Customizada

Você pode fornecer sua própria chave de idempotência:

```python
# Custom idempotency key
custom_key = "campaign_2024_new_year_greeting_patient_123"

message, is_duplicate = await sender.send_message(
    patient_id=patient_id,
    content="Feliz Ano Novo!",
    idempotency_key=custom_key
)
```

**Use casos para chaves customizadas**:
- Campanhas de mensagens em massa
- Mensagens agendadas com ID único
- Integrações externas com seus próprios IDs

## 🚀 Como Usar

### 1. Inicialização

```python
from app.services.idempotent_message_sender import IdempotentMessageSender
from app.integrations.evolution import get_evolution_client

# Inicializar serviço
sender = IdempotentMessageSender(
    db=db_session,
    redis=redis_client,
    evolution_client=evolution_client,
    cache_ttl=86400,  # 24 hours
    enable_cache=True
)
```

### 2. Enviar Mensagem

```python
# Enviar mensagem (idempotency automática)
message, is_duplicate = await sender.send_message(
    patient_id=patient.id,
    content="Olá! Como você está se sentindo hoje?",
    message_type=MessageType.TEXT
)

if is_duplicate:
    print(f"Mensagem já foi enviada anteriormente: {message.id}")
else:
    print(f"Nova mensagem enviada com sucesso: {message.id}")
```

### 3. Retry de Mensagem Falha

```python
# Retry com mesmo idempotency_key (seguro)
message, is_duplicate = await sender.retry_failed_message(
    message_id=failed_message_id
)

# is_duplicate será True se já foi enviada com sucesso entre tempo
```

### 4. Mensagem com Metadados

```python
# Mensagem com botões
message, is_duplicate = await sender.send_message(
    patient_id=patient.id,
    content="Você tomou sua medicação hoje?",
    message_type=MessageType.BUTTON,
    metadata={
        "buttons": [
            {"id": "yes", "text": "Sim"},
            {"id": "no", "text": "Não"}
        ]
    }
)
```

### 5. Mensagem Agendada

```python
from datetime import datetime, timedelta

# Agendar mensagem para daqui a 1 hora
scheduled_time = datetime.utcnow() + timedelta(hours=1)

message, is_duplicate = await sender.send_message(
    patient_id=patient.id,
    content="Lembrete: Hora de tomar sua medicação!",
    scheduled_for=scheduled_time
)
```

## 🗄️ Schema de Banco de Dados

### Tabela Messages

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    patient_id UUID NOT NULL REFERENCES patients(id),
    direction VARCHAR NOT NULL,  -- 'inbound' or 'outbound'
    type VARCHAR NOT NULL,       -- 'text', 'button', etc.
    content TEXT,
    message_metadata JSONB,
    
    -- IDEMPOTENCY (NEW)
    idempotency_key VARCHAR(255) NOT NULL,
    
    whatsapp_id VARCHAR(255),
    status VARCHAR NOT NULL,     -- 'pending', 'sent', 'delivered', etc.
    
    -- Timestamps
    scheduled_for TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Retry logic
    retry_count INTEGER DEFAULT 0,
    last_retry_at TIMESTAMP WITH TIME ZONE,
    failure_reason TEXT,
    next_retry_at TIMESTAMP WITH TIME ZONE
);

-- UNIQUE CONSTRAINT (enforces idempotency at database level)
CREATE UNIQUE INDEX idx_messages_patient_idempotency 
ON messages(patient_id, idempotency_key) 
WHERE idempotency_key IS NOT NULL;

-- INDEX for fast lookups
CREATE INDEX idx_messages_idempotency_key 
ON messages(idempotency_key);
```

## 📊 Redis Cache

### Estrutura de Cache

```
Key Pattern: idempotency:message:{idempotency_key}
TTL: 24 hours (86400 seconds)

Value (JSON):
{
    "id": "uuid-of-message",
    "patient_id": "uuid-of-patient",
    "direction": "outbound",
    "type": "text",
    "content": "Message content...",
    "status": "sent",
    "whatsapp_id": "evolution-api-message-id",
    "idempotency_key": "msg_abc123...",
    "sent_at": "2024-01-15T10:30:00Z",
    "created_at": "2024-01-15T10:29:55Z"
}
```

### Cache TTL (24 horas)

**Por que 24 horas?**
- ✅ Cobre janela típica de retry
- ✅ Previne spam imediato
- ✅ Memória razoável (auto-cleanup)
- ✅ Depois de 24h, consulta vai para DB

### Cache Miss Strategy

Se cache miss (não encontrado no Redis):
1. Consulta banco de dados
2. Se encontrado no DB → atualiza cache
3. Se não encontrado → envia mensagem
4. Após enviar → armazena em cache

## 🔄 Fluxo de Envio Detalhado

### Caso 1: Primeira Tentativa (Sucesso)

```
1. send_message(patient_id=123, content="Olá")
   ↓
2. Gera idempotency_key: msg_abc123...
   ↓
3. Check Redis Cache → MISS (não existe)
   ↓
4. Check Database → MISS (não existe)
   ↓
5. Cria mensagem no DB (status: PENDING)
   ↓
6. Envia via Evolution API
   ↓
7. Atualiza mensagem (status: SENT, whatsapp_id: xyz)
   ↓
8. Commit no DB
   ↓
9. Armazena em Redis Cache (TTL: 24h)
   ↓
10. Retorna (message, is_duplicate=False)
```

### Caso 2: Retry Imediato (Duplicata)

```
1. send_message(patient_id=123, content="Olá")  [mesmos parâmetros]
   ↓
2. Gera idempotency_key: msg_abc123...  [mesma chave]
   ↓
3. Check Redis Cache → HIT ✅ (encontrado)
   ↓
4. Retorna mensagem existente (is_duplicate=True)
   ↓
5. NÃO envia novamente (economiza API call)
```

### Caso 3: Race Condition (Concurrent Requests)

```
Request A e Request B simultâneos:

Request A:                          Request B:
  ↓                                   ↓
Check Cache → MISS                  Check Cache → MISS
  ↓                                   ↓
Check DB → MISS                     Check DB → MISS
  ↓                                   ↓
Create Message → OK                 Create Message → FAIL
  ↓                                   ↓
Send via API → OK                   (IntegrityError)
  ↓                                   ↓
Commit → OK                         Rollback
  ↓                                   ↓
Cache → OK                          Re-fetch from DB
  ↓                                   ↓
Return (False)                      Return (True) ✅

Result: Only ONE message sent!
```

**Proteção**: Unique constraint no banco garante que apenas uma mensagem é criada.

### Caso 4: Retry Após Falha

```
1. send_message() → FAIL (Evolution API timeout)
   ↓
2. Mensagem criada no DB (status: FAILED)
   ↓
3. NÃO armazena em cache (só sucessos)
   ↓
4. retry_failed_message(message_id)
   ↓
5. Usa mesmo idempotency_key da mensagem original
   ↓
6. Check Cache → MISS (não cacheou falha)
   ↓
7. Check DB → HIT (encontra mensagem FAILED)
   ↓
8. Tenta enviar novamente
   ↓
9. Se sucesso → atualiza status e cacheia
   ↓
10. Retorna (message, is_duplicate=False)
```

## 🧪 Testes

### Teste de Idempotência Básica

```python
import pytest
from app.services.idempotent_message_sender import IdempotentMessageSender

@pytest.mark.asyncio
async def test_idempotent_send(db, redis, evolution_client, patient):
    """Test that duplicate sends return same message."""
    sender = IdempotentMessageSender(db, redis, evolution_client)
    
    # First send
    message1, is_dup1 = await sender.send_message(
        patient_id=patient.id,
        content="Test message"
    )
    
    assert is_dup1 is False  # First send
    assert message1.status == MessageStatus.SENT
    
    # Duplicate send (same parameters)
    message2, is_dup2 = await sender.send_message(
        patient_id=patient.id,
        content="Test message"
    )
    
    assert is_dup2 is True  # Duplicate detected
    assert message1.id == message2.id  # Same message
    assert message1.idempotency_key == message2.idempotency_key
```

### Teste de Cache Hit

```python
@pytest.mark.asyncio
async def test_cache_hit(db, redis, evolution_client, patient):
    """Test that cache prevents database query."""
    sender = IdempotentMessageSender(db, redis, evolution_client)
    
    # First send (populates cache)
    message1, _ = await sender.send_message(
        patient_id=patient.id,
        content="Test message"
    )
    
    # Clear database query counter
    db_query_count_before = get_query_count()
    
    # Second send (should hit cache)
    message2, is_dup = await sender.send_message(
        patient_id=patient.id,
        content="Test message"
    )
    
    db_query_count_after = get_query_count()
    
    assert is_dup is True
    assert db_query_count_after == db_query_count_before  # No DB query
```

### Teste de Race Condition

```python
@pytest.mark.asyncio
async def test_concurrent_sends(db, redis, evolution_client, patient):
    """Test that concurrent sends only create one message."""
    sender = IdempotentMessageSender(db, redis, evolution_client)
    
    # Send same message concurrently
    results = await asyncio.gather(
        sender.send_message(patient_id=patient.id, content="Test"),
        sender.send_message(patient_id=patient.id, content="Test"),
        sender.send_message(patient_id=patient.id, content="Test"),
        return_exceptions=True
    )
    
    # All should succeed (no exceptions)
    assert all(isinstance(r, tuple) for r in results)
    
    # All should have same message ID
    message_ids = [r[0].id for r in results]
    assert len(set(message_ids)) == 1  # Only one unique ID
    
    # At least one should be is_duplicate=False
    duplicate_flags = [r[1] for r in results]
    assert False in duplicate_flags  # At least one is first
```

### Teste de Retry

```python
@pytest.mark.asyncio
async def test_retry_with_idempotency(db, redis, evolution_client, patient):
    """Test that retry uses same idempotency key."""
    sender = IdempotentMessageSender(db, redis, evolution_client)
    
    # Mock Evolution API to fail
    evolution_client.send_text_message = AsyncMock(
        side_effect=Exception("API timeout")
    )
    
    # First attempt (should fail)
    with pytest.raises(Exception):
        message1, _ = await sender.send_message(
            patient_id=patient.id,
            content="Test message"
        )
    
    # Get the failed message
    failed_message = db.query(Message).filter(
        Message.patient_id == patient.id,
        Message.status == MessageStatus.FAILED
    ).first()
    
    assert failed_message is not None
    idempotency_key_original = failed_message.idempotency_key
    
    # Mock Evolution API to succeed
    evolution_client.send_text_message = AsyncMock(
        return_value={"key": {"id": "whatsapp-123"}}
    )
    
    # Retry
    message2, is_dup = await sender.retry_failed_message(failed_message.id)
    
    assert is_dup is False  # Not duplicate (first success)
    assert message2.status == MessageStatus.SENT
    assert message2.idempotency_key == idempotency_key_original
```

## 🎯 Boas Práticas

### ✅ SEMPRE FAÇA

1. **Use o serviço IdempotentMessageSender**
   ```python
   # ✅ CORRETO
   from app.services.idempotent_message_sender import IdempotentMessageSender
   sender = IdempotentMessageSender(db, redis, evolution_client)
   message, _ = await sender.send_message(...)
   ```

2. **Deixe geração automática de chave (na maioria dos casos)**
   ```python
   # ✅ CORRETO (geração automática)
   message, _ = await sender.send_message(
       patient_id=patient.id,
       content="Mensagem"
   )
   ```

3. **Verifique o flag is_duplicate**
   ```python
   # ✅ CORRETO
   message, is_duplicate = await sender.send_message(...)
   
   if is_duplicate:
       logger.info("Message already sent, skipping notification")
   else:
       logger.info("New message sent")
       send_notification_to_admin()
   ```

4. **Use retry para mensagens falhas**
   ```python
   # ✅ CORRETO
   if message.status == MessageStatus.FAILED:
       message, _ = await sender.retry_failed_message(message.id)
   ```

### ❌ NUNCA FAÇA

1. **Não envie direto via Evolution API (bypass idempotency)**
   ```python
   # ❌ ERRADO
   evolution_client.send_text_message(phone, content)
   
   # ✅ CORRETO
   sender.send_message(patient_id, content)
   ```

2. **Não modifique idempotency_key manualmente no banco**
   ```python
   # ❌ ERRADO
   message.idempotency_key = "novo-valor"
   db.commit()
   ```

3. **Não ignore is_duplicate em lógica crítica**
   ```python
   # ❌ ERRADO
   message, _ = await sender.send_message(...)  # Ignora flag
   charge_customer()  # Cobra mesmo se for duplicata!
   
   # ✅ CORRETO
   message, is_duplicate = await sender.send_message(...)
   if not is_duplicate:
       charge_customer()  # Só cobra se realmente enviou
   ```

4. **Não use chaves customizadas sem necessidade**
   ```python
   # ❌ ERRADO (sem necessidade)
   idempotency_key = str(uuid.uuid4())  # Sempre único = sem proteção
   
   # ✅ CORRETO (deixa automático)
   # A geração automática é baseada em conteúdo
   ```

## 🔧 Troubleshooting

### Problema: Mensagens duplicadas mesmo com idempotência

**Causas possíveis**:
1. Redis desligado/indisponível
2. Idempotency keys diferentes (conteúdo ligeiramente diferente)
3. Timestamp muito distante (> 1 minuto)
4. Bypass do serviço IdempotentMessageSender

**Solução**:
```bash
# 1. Verificar Redis
redis-cli PING

# 2. Verificar logs
grep "idempotency key" logs/app.log | tail -20

# 3. Verificar mensagens no DB
psql $DATABASE_URL -c "
SELECT patient_id, content, idempotency_key, created_at, status
FROM messages
WHERE patient_id = 'uuid-aqui'
ORDER BY created_at DESC
LIMIT 10;
"

# 4. Verificar cache
redis-cli KEYS "idempotency:message:*"
```

### Problema: Retry não funciona

**Causas possíveis**:
1. Mensagem não está em estado FAILED
2. Idempotency key mudou
3. Cache retornando resultado antigo

**Solução**:
```python
# Verificar estado da mensagem
message = db.query(Message).get(message_id)
print(f"Status: {message.status}")
print(f"Idempotency Key: {message.idempotency_key}")

# Limpar cache se necessário
redis.delete(f"idempotency:message:{message.idempotency_key}")

# Retry
message, is_dup = await sender.retry_failed_message(message_id)
```

### Problema: Cache sempre Miss

**Causas possíveis**:
1. TTL muito curto
2. Redis reiniciando
3. Cache desabilitado

**Solução**:
```python
# Verificar configuração
sender = IdempotentMessageSender(
    db, redis, evolution_client,
    cache_ttl=86400,  # 24 hours
    enable_cache=True  # Verificar se True
)

# Verificar TTL no Redis
redis-cli TTL "idempotency:message:msg_abc123..."
```

## 📊 Métricas e Monitoramento

### Métricas Importantes

```python
# Prometheus metrics
message_send_total = Counter(
    'message_send_total',
    'Total message send attempts',
    ['is_duplicate', 'status']
)

idempotency_cache_hit = Counter(
    'idempotency_cache_hit',
    'Idempotency cache hits',
    ['hit_type']  # 'redis' or 'database'
)

message_duplicate_prevented = Counter(
    'message_duplicate_prevented',
    'Duplicate messages prevented',
    ['detection_method']  # 'cache' or 'database'
)
```

### Dashboard Queries

```sql
-- Taxa de duplicatas detectadas
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_attempts,
    COUNT(DISTINCT idempotency_key) as unique_messages,
    COUNT(*) - COUNT(DISTINCT idempotency_key) as duplicates_prevented
FROM message_send_log
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Top pacientes com tentativas duplicadas
SELECT 
    patient_id,
    COUNT(*) as attempts,
    COUNT(DISTINCT idempotency_key) as unique_messages
FROM messages
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY patient_id
HAVING COUNT(*) > COUNT(DISTINCT idempotency_key)
ORDER BY attempts DESC
LIMIT 10;
```

## 🆘 Suporte

Se encontrar problemas com idempotência:

1. Verifique logs do serviço
2. Verifique Redis status
3. Verifique constraint no banco de dados
4. Contate: backend-team@hormonia.com

---

**Última Atualização**: Janeiro 2024  
**Versão**: 1.0  
**Autor**: Sistema Hormonia - Backend Team