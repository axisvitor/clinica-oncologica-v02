# Relatório: Sistema de Tratamento de Erros e Compensações da Saga

**Data:** 2025-11-07  
**Sistema:** Patient Onboarding Saga - Clínica Oncológica v02  
**Analista:** Claude Code  

---

## 📋 Executive Summary

Este relatório apresenta uma análise detalhada do sistema de tratamento de erros e compensações da saga de onboarding de pacientes, incluindo taxonomia de erros, estratégias de retry em 3 níveis, mecanismos de compensação, fallbacks, alertas e recomendações de melhorias.

**Principais Descobertas:**
- ✅ Sistema robusto com 3 níveis de retry
- ✅ Compensações automáticas em ordem reversa
- ✅ Classificação inteligente de erros (6 categorias, 4 severidades)
- ⚠️ Gaps em circuit breakers para external services
- ⚠️ DLQ implementada mas sem processamento automático completo
- ⚠️ Sentry configurado mas não totalmente integrado

---

## 1. 🏷️ TAXONOMIA COMPLETA DE ERROS

### 1.1 Categorias de Erro (Error Categories)

#### 📨 MESSAGE_DELIVERY
**Descrição:** Falhas no envio de mensagens via WhatsApp/Evolution API  
**Severidade Típica:** MEDIUM a HIGH  
**Recovery Strategy:** RETRY_EXPONENTIAL  

**Subcategorias:**
- `ConnectionError` - Erro de conexão com Evolution API
- `TimeoutError` - Timeout na requisição
- `RateLimitError` - Limite de taxa excedido (429)
- `ServiceUnavailable` - Serviço temporariamente indisponível (503)

**Exemplo de Erro:**
```python
MessageDeliveryError(
    message="Failed to send WhatsApp message",
    patient_id=uuid,
    message_id=uuid,
    retry_count=2,
    last_error="Evolution API timeout after 30s"
)
```

---

#### 🔄 FLOW_PROCESSING
**Descrição:** Erros durante processamento de flows  
**Severidade Típica:** MEDIUM  
**Recovery Strategy:** RETRY_LINEAR  

**Subcategorias:**
- `FlowStateError` - Estado de flow inválido
- `FlowOperationError` - Operação de flow falhou
- `InvalidState` - Estado corrompido ou inconsistente
- `FlowNotFound` - Flow não encontrado

**Exemplo de Erro:**
```python
FlowProcessingError(
    message="Invalid flow state transition",
    patient_id=uuid,
    flow_type="initial_15_days",
    current_day=5,
    operation="advance_step"
)
```

---

#### 🌐 EXTERNAL_SERVICE
**Descrição:** Falhas em serviços externos (Gemini, Redis, APIs)  
**Severidade Típica:** MEDIUM a HIGH  
**Recovery Strategy:** RETRY_EXPONENTIAL (7 tentativas)  

**Subcategorias:**
- `AIServiceError` - Gemini/OpenAI falhou
- `RedisConnectionError` - Redis indisponível
- `APIError` - API externa falhou
- `AuthenticationError` - Falha de autenticação (não recuperável)

**Exemplo de Erro:**
```python
ExternalServiceError(
    message="Gemini API rate limit exceeded",
    service_name="gemini",
    error_code="RATE_LIMIT_EXCEEDED",
    is_recoverable=True,
    retry_after=60
)
```

---

#### 💾 DATA_CORRUPTION
**Descrição:** Corrupção ou inconsistência de dados  
**Severidade Típica:** HIGH a CRITICAL  
**Recovery Strategy:** ESCALATE_MANUAL (1 tentativa apenas)  

**Subcategorias:**
- `FlowStateCorruptionError` - Estado de flow corrompido
- `IntegrityError` - Violação de constraint do DB
- `InvalidData` - Dados inválidos detectados

**Exemplo de Erro:**
```python
FlowStateCorruptionError(
    message="Flow state data structure invalid",
    patient_id=uuid,
    flow_state_data={"corrupted": "data"},
    corruption_type="missing_required_fields"
)
```

---

#### ⚙️ SYSTEM_ERROR
**Descrição:** Erros de sistema (DB, recursos, etc)  
**Severidade Típica:** MEDIUM a CRITICAL  
**Recovery Strategy:** RETRY_LINEAR  

**Subcategorias:**
- `DatabaseError` - Erro de banco de dados
- `OperationalError` - Erro operacional do DB
- `MemoryError` - Falta de memória
- `DiskError` - Problemas de disco

**Exemplo de Erro:**
```python
DatabaseError(
    message="Database connection pool exhausted",
    operation="patient_create",
    table="patients",
    patient_id=uuid,
    is_recoverable=True
)
```

---

#### ✅ VALIDATION_ERROR
**Descrição:** Erros de validação de dados  
**Severidade Típica:** LOW  
**Recovery Strategy:** SKIP_AND_CONTINUE  

**Subcategorias:**
- `FlowValidationError` - Validação de dados de flow
- `SchemaValidationError` - Validação de schema
- `InputValidationError` - Entrada inválida

**Exemplo de Erro:**
```python
FlowValidationError(
    message="Invalid patient data",
    validation_errors={
        "email": "Invalid email format",
        "phone": "Phone number required"
    },
    patient_id=uuid,
    flow_type="onboarding"
)
```

---

### 1.2 Severidades de Erro (Error Severity)

#### 🟢 LOW
- Não impede funcionamento
- Recuperação automática
- Log: WARNING
- Exemplo: Validation errors, dados faltando não-críticos

#### 🟡 MEDIUM  
- Impacta operação mas recuperável
- Retry automático
- Log: ERROR
- Exemplo: Message delivery timeout, flow processing errors

#### 🟠 HIGH
- Impacto significativo
- Retry com limite
- Log: ERROR + Alert
- Exemplo: External service failures, data corruption

#### 🔴 CRITICAL
- Sistema comprometido
- Escalação imediata
- Log: CRITICAL + Alert + Email
- Exemplo: Database down, memory exhausted, massive data corruption

---

## 2. 🔁 ESTRATÉGIAS DE RETRY (3 NÍVEIS)

### 2.1 Nível 1: In-Step Retry (Saga Orchestrator)

**Localização:** `app/coordination/saga_orchestrator.py` (linhas 286-334)

**Características:**
- **Max Retries:** 3 tentativas
- **Backoff:** Exponencial (1s → 2s → 4s → 8s → 16s → max 30s)
- **Scope:** Dentro de cada step da saga
- **Rollback on Failure:** Sim, com db.rollback() após cada falha

**Implementação:**
```python
retry_delay = 1  # Start with 1 second
while step.retry_count <= step.max_retries:
    try:
        result = await step.action(saga_state.context)
        # Success!
        return True, result
    except Exception as e:
        step.retry_count += 1
        if step.retry_count > step.max_retries:
            return False, None
        # Exponential backoff
        await self._sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 30)  # Max 30 seconds
```

**Steps que usam:**
1. `create_patient` - Criação de paciente no DB
2. `create_flow_state` - Criação de flow state
3. `send_initial_message` - Envio de mensagem inicial

**Vantagens:**
- ✅ Rápido recovery para erros transientes
- ✅ Não requer persistência externa
- ✅ Limpeza de DB session entre retries

**Limitações:**
- ❌ Não persiste progresso entre retries
- ❌ Se o processo morrer, perde o estado

---

### 2.2 Nível 2: Saga-Level Retry (Celery Tasks)

**Localização:** `app/tasks/saga_retry.py`

**Características:**
- **Max Retries:** 3 tentativas (configurável via `SAGA_MAX_RETRIES`)
- **Backoff:** Exponencial (1min → 2min → 4min)
- **Scope:** Saga completa
- **Persistence:** Database + Redis

**Configuração:**
```python
# Backoff formula: base_delay * (2 ^ retry_count)
- Retry 1: 60s (1 min)
- Retry 2: 120s (2 min)  
- Retry 3: 240s (4 min)
- Max delay: 600s (10 min)
```

**Fluxo de Retry:**
```
1. Saga fails → Status = FAILED
2. Persist saga to database
3. Celery task: retry_patient_onboarding_saga
4. Check retry_count < max_retries
5. Calculate exponential backoff
6. Schedule retry task with countdown
7. Execute resume_saga() from last step
8. If success: Status = COMPLETED
9. If fail again: Increment retry_count, repeat
10. If max retries: Status = FAILED + Alert Admin
```

**Tarefas Celery:**
```python
@shared_task(
    name="retry_patient_onboarding_saga",
    max_retries=3,
    default_retry_delay=60
)
def retry_patient_onboarding_saga(saga_id: str):
    # Calculate backoff
    backoff_seconds = base_delay * (2 ** retry_count)
    
    # Check if ready for retry
    if datetime.utcnow() < next_retry_time:
        return  # Wait for backoff
    
    # Increment retry count
    saga.retry_count += 1
    saga.last_retry_at = datetime.utcnow()
    
    # Resume saga from last step
    result = await orchestrator.resume_saga(saga_id)
    
    if result["status"] == "completed":
        # Success!
        saga.status = SagaStatus.COMPLETED
    else:
        # Still failing, will retry again or escalate
```

**Periodic Scanner:**
```python
@shared_task(name="scan_and_retry_failed_sagas")
def scan_and_retry_failed_sagas():
    # Runs every 5 minutes
    # Finds failed sagas eligible for retry
    failed_sagas = db.query(PatientOnboardingSaga).filter(
        status.in_([FAILED, COMPENSATING]),
        retry_count < max_retries
    )
    
    for saga in failed_sagas:
        # Schedule retry with exponential backoff
        retry_patient_onboarding_saga.apply_async(
            args=[str(saga.id)],
            countdown=calculate_exponential_backoff(saga.retry_count)
        )
```

**Vantagens:**
- ✅ Persiste estado no database
- ✅ Sobrevive a restarts de processo
- ✅ Retry automático via Celery Beat
- ✅ Escalação automática após max retries

**Limitações:**
- ❌ Depende de Celery estar rodando
- ❌ Delay mínimo de 1 minuto

---

### 2.3 Nível 3: Flow Error Handler (Granular Retry)

**Localização:** `app/domain/errors/flows/`

**Características:**
- **Max Retries:** Variável por categoria
  - MESSAGE_DELIVERY: 5
  - FLOW_PROCESSING: 3
  - EXTERNAL_SERVICE: 7
  - DATA_CORRUPTION: 1
  - SYSTEM_ERROR: 2
  - VALIDATION_ERROR: 1
- **Backoff:** Configurável (exponential ou linear)
- **Scope:** Operações específicas de flow
- **Persistence:** Redis

**Delays Configurados:**
```python
# Exponential
RETRY_EXPONENTIAL: [60, 300, 900, 1800, 3600]  
# 1min, 5min, 15min, 30min, 1hr

# Linear
RETRY_LINEAR: [300, 300, 300, 300, 300]  
# 5min intervals
```

**Recovery Strategies:**
1. **RETRY_EXPONENTIAL** - Para erros transientes (network, timeouts)
2. **RETRY_LINEAR** - Para erros de processamento
3. **FALLBACK_MESSAGE** - Mensagem de fallback quando AI falha
4. **SKIP_AND_CONTINUE** - Pula operação e continua
5. **PAUSE_FLOW** - Pausa flow por 1 hora
6. **RESET_FLOW** - Reset para estado anterior
7. **ESCALATE_MANUAL** - Escalação imediata

**Exemplo de Uso:**
```python
# Classificar erro
category, severity = classifier.classify_error(error)

# Criar record
error_record = ErrorRecord(
    category=category,
    severity=severity,
    max_recovery_attempts=config.max_retry_attempts[category]
)

# Determinar estratégia
strategy = selector.determine_recovery_strategy(category, severity)

# Executar recovery
action = RecoveryActionFactory.create_action(strategy)
result = await action.execute(error_record, context)
```

**Vantagens:**
- ✅ Retry personalizado por tipo de erro
- ✅ Múltiplas estratégias de recovery
- ✅ Fallbacks inteligentes
- ✅ Métricas detalhadas

**Limitações:**
- ❌ Complexidade adicional
- ❌ Depende de Redis para scheduling

---

### 2.4 Resumo Comparativo dos 3 Níveis

| Aspecto | Nível 1 (In-Step) | Nível 2 (Saga) | Nível 3 (Flow Handler) |
|---------|-------------------|----------------|------------------------|
| **Scope** | Single step | Saga completa | Operação específica |
| **Max Retries** | 3 | 3 | 1-7 (variável) |
| **Delay Inicial** | 1s | 60s | 60s-300s |
| **Backoff** | Exponencial | Exponencial | Configurável |
| **Max Delay** | 30s | 600s | 3600s (1hr) |
| **Persistence** | Memory | Database | Redis |
| **Auto Recovery** | Sim | Sim (Celery) | Sim (Redis) |
| **Survives Restart** | Não | Sim | Sim |
| **Fallback** | Compensação | Resume from step | Multiple strategies |

---

## 3. 🔙 FLUXO DE COMPENSAÇÃO

### 3.1 Compensating Transactions

**Princípios:**
- Execução em ordem reversa dos steps
- Idempotência garantida
- Best-effort (não falha se compensação falhar)
- Logging completo

**Ordem de Compensação:**
```
Step 3: send_initial_message
  └── Compensation: send_cancellation_message
       ↓
Step 2: create_flow_state  
  └── Compensation: delete_flow_state
       ↓
Step 1: create_patient
  └── Compensation: delete_patient
```

### 3.2 Implementação das Compensações

#### Step 1: Delete Patient
```python
async def _delete_patient_compensation(context: Dict[str, Any]) -> Optional[bool]:
    patient_id = context.get("patient_id")
    if not patient_id:
        return None  # Nothing to compensate
    
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient:
        db.delete(patient)
        db.flush()
        logger.info(f"✅ Patient deleted: {patient_id}")
        return True
    
    return None
```

**Idempotência:** Retorna None se paciente não existe (já deletado)

---

#### Step 2: Delete Flow State
```python
async def _delete_flow_state_compensation(context: Dict[str, Any]) -> Optional[bool]:
    flow_state_id = context.get("flow_state_id")
    if not flow_state_id:
        return None
    
    flow_state = db.query(PatientFlowState).filter(
        PatientFlowState.id == flow_state_id
    ).first()
    
    if flow_state:
        db.delete(flow_state)
        db.flush()
        logger.info(f"✅ Flow state deleted: {flow_state_id}")
        return True
    
    return None
```

**Idempotência:** Retorna None se flow state não existe

---

#### Step 3: Send Cancellation Message
```python
async def _send_cancellation_message_compensation(context: Dict[str, Any]) -> Optional[Message]:
    patient_id = context.get("patient_id")
    if not patient_id:
        return None
    
    try:
        cancellation_msg = (
            "Desculpe, houve um problema ao processar seu cadastro. "
            "Por favor, tente novamente mais tarde."
        )
        
        message, _ = await message_sender.send_message(
            patient_id=patient_id,
            content=cancellation_msg,
            message_type=MessageType.TEXT,
            idempotency_key=f"onboarding_{patient_id}_cancellation"
        )
        
        logger.info(f"✅ Cancellation message sent: {message.id}")
        return message
    
    except Exception as e:
        logger.error(f"Failed to send cancellation message: {e}")
        return None  # Best-effort, don't fail saga
```

**Idempotência:** Usa idempotency_key para evitar duplicatas  
**Best-Effort:** Não falha se envio falhar (apenas log)

---

### 3.3 Fluxo de Compensação Completo

```
┌─────────────────────────────────────────┐
│  Step 2 Fails (create_flow_state)      │
│  Status: COMPENSATING                  │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Compensate Step 1 (delete_patient)     │
│  - Query patient by ID                  │
│  - Delete from database                 │
│  - db.flush()                          │
│  - Log success                         │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Mark saga as COMPENSATED              │
│  - saga.status = COMPENSATED           │
│  - saga.completed_at = now()           │
│  - db.commit()                         │
└─────────────────────────────────────────┘
```

**Tratamento de Falhas em Compensação:**
```python
if not comp_success:
    logger.critical(f"⚠️ Compensation failed for step: {step.name}")
    # Continua para próxima compensação
    # Não para o processo de compensação
```

---

### 3.4 Persistência de Saga Compensada

```python
# Criar record no database
saga_record = SagaModel(
    id=saga_id,
    patient_id=patient_id,
    status=ModelSagaStatus.COMPENSATED,  # ← Status final
    current_step=saga_state.context.get("last_completed_step", 0),
    error_message=saga_state.error,
    patient_data=patient_data_json,
    execution_log=[],
    started_at=saga_state.created_at
)

db.add(saga_record)
db.commit()
```

**Auditoria:**
- Saga completa registrada no DB
- Erro original preservado
- Patient data preservado para análise
- Logs de compensação disponíveis

---

## 4. 🛡️ FALLBACK MECHANISMS

### 4.1 Saga Mode vs Direct Mode

**Configuração:**
```python
# settings.py
ENABLE_SAGA_MODE = True  # Feature flag
ENABLE_AUTO_FLOW_ENROLLMENT = True
ENABLE_WHATSAPP_ON_REGISTRATION = True
```

**Fallback Logic:**
```python
try:
    if settings.ENABLE_SAGA_MODE:
        # Try saga pattern
        patient = await saga_orchestrator.execute_patient_onboarding_saga(
            patient_data, doctor_id
        )
    else:
        # Fallback to direct mode
        patient = await create_patient_direct(patient_data, doctor_id)
except SagaException:
    # Saga failed, try direct mode as fallback
    logger.warning("Saga failed, falling back to direct mode")
    patient = await create_patient_direct(patient_data, doctor_id)
```

---

### 4.2 Graceful Degradation

#### Message Delivery Fallback
```python
# Primary: Evolution API
try:
    await evolution_client.send_message(phone, content)
except EvolutionAPIError:
    # Fallback 1: Queue for later
    await message_queue.enqueue(patient_id, content)
    # Fallback 2: Email notification
    await email_service.send_notification(patient.email, content)
```

#### AI Service Fallback
```python
# Primary: Gemini AI
try:
    response = await gemini_client.generate(prompt)
except AIServiceError:
    # Fallback: Template-based message
    response = get_template_message(patient_name, context)
```

#### Redis Fallback
```python
# Primary: Redis cache
try:
    data = await redis.get(key)
except RedisConnectionError:
    # Fallback: In-memory cache
    data = memory_cache.get(key)
    if data is None:
        # Ultimate fallback: Database query
        data = await db.query(...).first()
```

---

### 4.3 Circuit Breaker Pattern

**Localização:** `app/services/error_recovery.py` (linhas 153-174)

**Implementação:**
```python
# Circuit breaker para external services
circuit_key = f"circuit_breaker:{service_name}"
failure_count = await redis.get(circuit_key)

if failure_count >= 5:  # Threshold
    # Circuit OPEN
    logger.warning(f"Circuit breaker open for: {service_name}")
    await activate_fallback_mode(service_name)
    return True  # Use fallback

# Circuit CLOSED - try service
try:
    result = await external_service.call()
    # Success - reset circuit
    await redis.delete(circuit_key)
except Exception:
    # Failure - increment counter
    await redis.incr(circuit_key)
    await redis.expire(circuit_key, 3600)  # Reset after 1 hour
```

**Estados:**
- **CLOSED** - Normal operation
- **OPEN** - Service unavailable, use fallback
- **HALF-OPEN** - Auto-reset after 1 hour

---

### 4.4 Dead Letter Queue (DLQ)

**Localização:** `app/services/dlq_service.py`

**Features:**
- Categorização automática de erros (transient vs permanent)
- Retry automático para erros transientes
- Dashboard administrativo
- Métricas Prometheus

**Fluxo DLQ:**
```
1. Message delivery fails
2. Categorize error (transient/permanent/unknown)
3. Add to DLQ table
4. If transient: Schedule auto-retry
5. If permanent: Alert admin
6. Retry delays: 1min → 5min → 15min → 1h → 2h
7. Max retries: 5
8. After max: Status = MAX_RETRIES_EXCEEDED
```

**Categorias de Erro:**
```python
# Transient errors (auto-retry)
TRANSIENT_ERRORS = [
    "ConnectionError",
    "TimeoutError", 
    "ServiceUnavailable",
    "RateLimitExceeded",
    "HTTPError: 429",
    "HTTPError: 503"
]

# Permanent errors (manual intervention)
PERMANENT_ERRORS = [
    "ValidationError",
    "AuthenticationError",
    "NotFoundError",
    "HTTPError: 400",
    "HTTPError: 401",
    "HTTPError: 404"
]
```

**Retry Automático:**
```python
def _schedule_automatic_retry(failed_message: FailedMessage):
    if failed_message.retry_count >= MAX_RETRY_ATTEMPTS:
        failed_message.status = DLQStatus.MAX_RETRIES_EXCEEDED
        return
    
    # Exponential backoff
    delay_seconds = RETRY_DELAYS[min(retry_count, len(RETRY_DELAYS) - 1)]
    next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
    
    failed_message.status = DLQStatus.RETRY_SCHEDULED
    failed_message.metadata["next_retry_at"] = next_retry_at.isoformat()
    db.commit()
```

---

## 5. 🚨 SISTEMA DE ALERTAS

### 5.1 Níveis de Alertas

#### Level 1: Logging
**Severidade:** LOW  
**Destino:** Logs de aplicação  
**Exemplos:** Validation errors, retries bem-sucedidos

```python
logger.info("✅ Saga step completed successfully")
logger.warning("⚠️ Retry scheduled for error")
```

#### Level 2: Error Tracking
**Severidade:** MEDIUM  
**Destino:** Error tracking service (Sentry)  
**Exemplos:** Failed steps, compensações

```python
capture_message(
    f"Saga retry successful: {saga_id}",
    level="info",
    extra={"saga_id": saga_id, "retry_count": retry_count}
)
```

#### Level 3: Database Alerts
**Severidade:** HIGH  
**Destino:** Alert table no database  
**Exemplos:** Max retries exceeded

```python
alert = Alert(
    alert_type=AlertType.SYSTEM,
    priority=AlertPriority.HIGH,
    title=f"Patient Onboarding Saga Failed: {saga_id}",
    message=f"Saga exceeded max retry attempts ({retry_count})",
    metadata={
        "saga_id": str(saga_id),
        "patient_id": str(patient_id),
        "retry_count": retry_count
    },
    doctor_id=saga.doctor_id
)
db.add(alert)
```

#### Level 4: Email Alerts
**Severidade:** CRITICAL  
**Destino:** Admin email  
**Exemplos:** Saga completamente falhada

```python
subject = f"[URGENT] Patient Onboarding Saga Failed: {saga_id}"
body = f"""
<h2>Patient Onboarding Saga Failed</h2>
<p>Saga exceeded max retries and requires manual intervention.</p>
<ul>
    <li>Saga ID: {saga_id}</li>
    <li>Patient ID: {patient_id}</li>
    <li>Retry Count: {retry_count}</li>
    <li>Error: {error_message}</li>
</ul>
"""
await send_email(admin_email, subject, body, priority="high")
```

---

### 5.2 Escalação de Alertas

**Fluxo de Escalação:**
```
Error Occurs
    ↓
Retry 1 (1 min) → Log: INFO
    ↓
Retry 2 (2 min) → Log: WARNING
    ↓
Retry 3 (4 min) → Sentry: capture_message
    ↓
Max Retries → Database Alert (HIGH)
    ↓
Still Failed → Email Admin (CRITICAL)
```

**Timeline:**
- 0min: Error occurs
- 1min: First retry
- 3min: Second retry  
- 7min: Third retry (Sentry notified)
- 7min+: Database alert created
- 7min+: Admin email sent

---

### 5.3 Métricas Prometheus

**Localização:** `app/monitoring/dlq_metrics.py`

**Métricas Implementadas:**
```python
# DLQ queue size
dlq_queue_size = Gauge(
    'dlq_queue_size',
    'Current size of DLQ queue',
    ['category', 'status']
)

# Retry attempts
dlq_retry_attempts = Histogram(
    'dlq_retry_attempts',
    'Number of retry attempts before resolution',
    ['category']
)

# Processing time
dlq_retry_duration = Histogram(
    'dlq_retry_duration_seconds',
    'Time taken to retry message',
    ['category', 'status']
)

# Message age
dlq_oldest_message_age = Gauge(
    'dlq_oldest_message_age_seconds',
    'Age of oldest message in DLQ',
    ['category']
)
```

**Dashboard:**
- Total messages em DLQ
- Taxa de sucesso de retries
- Distribuição de categorias
- Tempo médio de recovery

---

### 5.4 WebSocket Alerts

**Localização:** `app/domain/errors/flows/recovery_strategy.py` (linhas 359-367)

**Implementação:**
```python
# Publish escalation event via WebSocket
await websocket_events.publish_alert_event(
    event_type=WebSocketEventType.ALERT_CREATED,
    patient_id=error_record.context.patient_id,
    alert_type="flow_error_escalation",
    priority="high" if severity == CRITICAL else "medium",
    message=f"Flow error requires manual intervention",
    metadata=escalation_data
)
```

**Real-Time Notifications:**
- Admin dashboard recebe alertas imediatamente
- Filtros por severidade (high/medium/low)
- Ações rápidas disponíveis (retry manual, discard)

---

## 6. ⚠️ GAPS CRÍTICOS IDENTIFICADOS

### 6.1 Circuit Breakers Incompletos

**Problema:**
- Circuit breaker implementado apenas em `error_recovery.py`
- Não aplicado em todas as integrações externas
- Sem coordenação entre múltiplas instâncias

**Impact:** MEDIUM  
**Arquivos Afetados:**
- `app/integrations/evolution.py` - Sem circuit breaker
- `app/integrations/gemini_client.py` - Sem circuit breaker
- `app/core/redis_manager.py` - Sem circuit breaker

**Recomendação:**
```python
# Implementar circuit breaker decorator
@circuit_breaker(
    failure_threshold=5,
    recovery_timeout=60,
    fallback=use_cached_response
)
async def call_external_api(...):
    ...
```

---

### 6.2 DLQ Sem Processamento Automático Completo

**Problema:**
- DLQ implementada mas retry worker não está rodando
- Função `process_scheduled_retries()` existe mas não está em Celery Beat
- Mensagens ficam paradas em DLQ indefinidamente

**Impact:** HIGH  
**Arquivos Afetados:**
- `app/celery_app.py` - Falta task em beat_schedule
- `app/services/dlq_service.py` - Worker não integrado

**Recomendação:**
```python
# Adicionar em celery_app.py beat_schedule
"process-dlq-retries": {
    "task": "app.tasks.dlq.process_scheduled_retries",
    "schedule": 300.0,  # Every 5 minutes
    "kwargs": {"limit": 50}
},
```

---

### 6.3 Sentry Integration Incompleta

**Problema:**
- Sentry configurado mas não totalmente integrado
- `capture_exception` e `capture_message` usados mas sem contexto rico
- Não há breadcrumbs para debug

**Impact:** MEDIUM  
**Arquivos Afetados:**
- `app/tasks/saga_retry.py` - Usa Sentry mas sem contexto
- `app/coordination/saga_orchestrator.py` - Sem Sentry

**Recomendação:**
```python
# Enriquecer contexto Sentry
import sentry_sdk

with sentry_sdk.configure_scope() as scope:
    scope.set_tag("saga_id", saga_id)
    scope.set_tag("patient_id", patient_id)
    scope.set_context("saga", {
        "status": saga.status,
        "retry_count": saga.retry_count,
        "current_step": saga.current_step
    })
    scope.add_breadcrumb(
        category="saga",
        message=f"Step {step.name} failed",
        level="error"
    )
    sentry_sdk.capture_exception(error)
```

---

### 6.4 Idempotência Não Garantida em Todos os Steps

**Problema:**
- Apenas step de mensagem usa `idempotency_key`
- Create patient e create flow state podem duplicar em retry

**Impact:** HIGH  
**Arquivos Afetados:**
- `app/coordination/saga_orchestrator.py` - Steps 1 e 2

**Implementação Atual:**
```python
# ✅ Step 3 - Idempotente
message, is_duplicate = await message_sender.send_message(
    patient_id=patient_id,
    content=initial_message,
    idempotency_key=f"onboarding_{patient_id}_initial"  # ← Idempotency key
)

# ❌ Step 1 - NÃO Idempotente
patient = Patient(
    name=patient_data["name"],
    phone=patient_data["phone"],
    # ...
)
db.add(patient)
db.flush()
# Se retry, cria paciente duplicado!
```

**Recomendação:**
```python
# Step 1 - Idempotente
existing = db.query(Patient).filter(
    or_(
        Patient.email == email,
        Patient.phone == phone
    )
).first()

if existing:
    logger.info(f"Patient already exists: {existing.id}")
    return existing  # Idempotente!

patient = Patient(...)
db.add(patient)
db.flush()
```

---

### 6.5 Falta de Timeout em Operações Assíncronas

**Problema:**
- Saga steps não têm timeout
- Pode ficar travado indefinidamente

**Impact:** HIGH  
**Arquivos Afetados:**
- `app/coordination/saga_orchestrator.py` - Sem timeout nos steps

**Recomendação:**
```python
import asyncio

# Adicionar timeout
try:
    result = await asyncio.wait_for(
        step.action(saga_state.context),
        timeout=30.0  # 30 segundos
    )
except asyncio.TimeoutError:
    logger.error(f"Step {step.name} timed out after 30s")
    raise StepTimeoutError(f"Step {step.name} exceeded timeout")
```

---

### 6.6 Logs Não Estruturados

**Problema:**
- Logs em formato texto, dificulta parsing
- Sem correlação entre logs de uma mesma saga

**Impact:** MEDIUM  
**Arquivos Afetados:**
- Todos os arquivos de saga

**Recomendação:**
```python
# Usar structured logging
import structlog

logger = structlog.get_logger()

logger.info(
    "saga_step_completed",
    saga_id=saga_id,
    step_name=step.name,
    duration_ms=duration,
    patient_id=patient_id
)
```

---

### 6.7 Métricas de Performance Ausentes

**Problema:**
- Não há métricas de latência de saga
- Não há SLO/SLA definidos

**Impact:** MEDIUM  
**Arquivos Afetados:**
- Sistema todo

**Recomendação:**
```python
# Adicionar métricas Prometheus
from prometheus_client import Histogram

saga_duration = Histogram(
    'saga_duration_seconds',
    'Duration of saga execution',
    ['saga_type', 'status']
)

with saga_duration.labels(
    saga_type='patient_onboarding',
    status='completed'
).time():
    await execute_saga(...)
```

---

## 7. 📊 RECOMENDAÇÕES DE MELHORIAS

### 7.1 Prioridade CRÍTICA

#### 1. Garantir Idempotência Completa
**Prazo:** Imediato  
**Esforço:** 4 horas  
**Impacto:** Evita duplicação de dados

**Implementação:**
```python
# app/coordination/saga_orchestrator.py

async def _create_patient_action(self, context: Dict[str, Any]) -> Patient:
    patient_data = context["patient_data"]
    
    # ✅ Idempotency check
    existing = self.db.query(Patient).filter(
        or_(
            Patient.email == patient_data.get("email"),
            Patient.phone == patient_data["phone"]
        )
    ).first()
    
    if existing:
        context["patient_id"] = existing.id
        context["patient"] = existing
        logger.info(f"✅ Using existing patient (idempotent): {existing.id}")
        return existing
    
    # Create new patient
    patient = Patient(**patient_data)
    self.db.add(patient)
    self.db.flush()
    
    context["patient_id"] = patient.id
    context["patient"] = patient
    
    return patient

async def _create_flow_state_action(self, context: Dict[str, Any]) -> PatientFlowState:
    patient_id = context["patient_id"]
    
    # ✅ Idempotency check
    existing = self.db.query(PatientFlowState).filter(
        PatientFlowState.patient_id == patient_id,
        PatientFlowState.template_version_id == template_version.id
    ).first()
    
    if existing:
        context["flow_state_id"] = existing.id
        context["flow_state"] = existing
        logger.info(f"✅ Using existing flow state (idempotent): {existing.id}")
        return existing
    
    # Create new flow state
    flow_state = PatientFlowState(...)
    self.db.add(flow_state)
    self.db.flush()
    
    return flow_state
```

---

#### 2. Adicionar Timeouts em Steps
**Prazo:** 1 semana  
**Esforço:** 2 horas  
**Impacto:** Evita travamentos

**Implementação:**
```python
import asyncio

async def _execute_step_with_timeout(
    self, step: SagaStep, saga_state: SagaState, timeout: int = 30
) -> tuple[bool, Any]:
    try:
        result = await asyncio.wait_for(
            self._execute_step(step, saga_state),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"Step {step.name} timed out after {timeout}s")
        step.status = SagaStepStatus.FAILED
        step.error = f"Timeout after {timeout}s"
        return False, None
```

---

#### 3. Ativar DLQ Worker
**Prazo:** Imediato  
**Esforço:** 1 hora  
**Impacto:** Retry automático funciona

**Implementação:**
```python
# app/celery_app.py

celery_app.conf.beat_schedule = {
    # ... existing tasks ...
    
    "process-dlq-retries": {
        "task": "app.tasks.dlq.process_scheduled_retries",
        "schedule": 300.0,  # Every 5 minutes
        "kwargs": {"limit": 50}
    },
    
    "cleanup-old-dlq-messages": {
        "task": "app.tasks.dlq.cleanup_old_messages",
        "schedule": 86400.0,  # Daily
        "kwargs": {"days_old": 30}
    },
}
```

---

### 7.2 Prioridade ALTA

#### 4. Implementar Circuit Breakers Globais
**Prazo:** 2 semanas  
**Esforço:** 8 horas  
**Impacto:** Protege contra cascading failures

**Implementação:**
```python
# app/resilience/circuit_breaker/global_breaker.py

from app.resilience.circuit_breaker.breaker import CircuitBreaker

# Evolution API
evolution_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=EvolutionAPIError
)

# Gemini API
gemini_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=120,
    expected_exception=AIServiceError
)

# Redis
redis_breaker = CircuitBreaker(
    failure_threshold=10,
    recovery_timeout=30,
    expected_exception=RedisConnectionError
)

# Usar nos serviços
@evolution_breaker
async def send_whatsapp_message(...):
    ...

@gemini_breaker
async def generate_ai_response(...):
    ...
```

---

#### 5. Enriquecer Sentry Integration
**Prazo:** 1 semana  
**Esforço:** 4 horas  
**Impacto:** Melhor debugging

**Implementação:**
```python
# app/coordination/saga_orchestrator.py

import sentry_sdk

async def execute_saga(self, saga_state: SagaState) -> SagaState:
    # Configure Sentry scope
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("saga_id", saga_state.saga_id)
        scope.set_tag("saga_type", saga_state.saga_type)
        scope.set_context("saga", {
            "status": saga_state.status.value,
            "steps": len(saga_state.steps),
            "created_at": saga_state.created_at.isoformat()
        })
        
        # Add patient context
        patient_id = saga_state.context.get("patient_id")
        if patient_id:
            scope.set_user({"id": str(patient_id)})
        
        try:
            # Execute steps
            for i, step in enumerate(saga_state.steps):
                scope.add_breadcrumb(
                    category="saga",
                    message=f"Executing step: {step.name}",
                    level="info"
                )
                
                success, result = await self._execute_step(step, saga_state)
                
                if not success:
                    scope.add_breadcrumb(
                        category="saga",
                        message=f"Step failed: {step.name}",
                        level="error",
                        data={"error": step.error}
                    )
                    sentry_sdk.capture_message(
                        f"Saga step failed: {step.name}",
                        level="error"
                    )
                    
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise
```

---

#### 6. Adicionar Métricas de Performance
**Prazo:** 2 semanas  
**Esforço:** 6 horas  
**Impacto:** Visibilidade operacional

**Implementação:**
```python
# app/monitoring/saga_metrics.py

from prometheus_client import Histogram, Counter, Gauge

# Duration metrics
saga_duration_seconds = Histogram(
    'saga_duration_seconds',
    'Duration of saga execution',
    ['saga_type', 'status'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

step_duration_seconds = Histogram(
    'saga_step_duration_seconds',
    'Duration of individual saga steps',
    ['saga_type', 'step_name', 'status'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30]
)

# Count metrics
saga_total = Counter(
    'saga_total',
    'Total number of sagas executed',
    ['saga_type', 'status']
)

saga_retry_total = Counter(
    'saga_retry_total',
    'Total number of saga retries',
    ['saga_type', 'step_name']
)

# Gauge metrics
saga_active = Gauge(
    'saga_active',
    'Number of currently active sagas',
    ['saga_type']
)

# Use in orchestrator
with saga_duration_seconds.labels(
    saga_type='patient_onboarding',
    status='completed'
).time():
    result = await self.execute_saga(saga_state)

saga_total.labels(
    saga_type='patient_onboarding',
    status=saga_state.status.value
).inc()
```

---

### 7.3 Prioridade MÉDIA

#### 7. Implementar Structured Logging
**Prazo:** 3 semanas  
**Esforço:** 8 horas  
**Impacto:** Melhor observabilidade

**Implementação:**
```python
# app/core/logging_config.py

import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage
logger.info(
    "saga_started",
    saga_id=saga_id,
    saga_type="patient_onboarding",
    patient_id=patient_id
)

logger.error(
    "saga_step_failed",
    saga_id=saga_id,
    step_name=step.name,
    error=str(error),
    retry_count=retry_count
)
```

---

#### 8. Dashboard de Monitoramento
**Prazo:** 1 mês  
**Esforço:** 16 horas  
**Impacto:** Visibilidade operacional

**Features:**
- Real-time saga status
- Success/failure rates
- Average duration
- Retry distribution
- DLQ queue size
- Circuit breaker status

**Stack:**
- Prometheus (métricas)
- Grafana (visualização)
- Alert Manager (alertas)

---

#### 9. Testes de Resiliência
**Prazo:** 1 mês  
**Esforço:** 20 horas  
**Impacto:** Confiabilidade

**Implementação:**
```python
# tests/integration/test_saga_resilience.py

import pytest

@pytest.mark.asyncio
async def test_saga_retries_on_transient_error():
    """Test saga retries on transient database error"""
    # Simulate DB timeout on first attempt
    with mock.patch('app.models.Patient', side_effect=[
        OperationalError("Connection timeout"),
        Patient(...)  # Success on retry
    ]):
        saga = await orchestrator.execute_patient_onboarding_saga(
            patient_data, doctor_id
        )
        
        assert saga.status == SagaStatus.COMPLETED
        assert saga.steps[0].retry_count == 1

@pytest.mark.asyncio
async def test_saga_compensates_on_failure():
    """Test saga compensates when step fails"""
    # Fail on step 2
    with mock.patch('app.models.PatientFlowState', side_effect=Exception("DB error")):
        saga = await orchestrator.execute_patient_onboarding_saga(
            patient_data, doctor_id
        )
        
        assert saga.status == SagaStatus.COMPENSATED
        # Verify patient was deleted (compensated)
        patient = db.query(Patient).filter(...).first()
        assert patient is None

@pytest.mark.asyncio  
async def test_saga_idempotency():
    """Test saga is idempotent on retry"""
    saga1 = await orchestrator.execute_patient_onboarding_saga(
        patient_data, doctor_id
    )
    
    # Execute again with same data
    saga2 = await orchestrator.execute_patient_onboarding_saga(
        patient_data, doctor_id
    )
    
    # Should reuse same patient
    assert saga1.context["patient_id"] == saga2.context["patient_id"]
    # Should not create duplicate
    count = db.query(Patient).filter(Patient.email == email).count()
    assert count == 1
```

---

## 8. 📈 MÉTRICAS SUGERIDAS

### 8.1 SLIs (Service Level Indicators)

```yaml
# Saga Success Rate
- Name: saga_success_rate
  Target: >= 95%
  Formula: (successful_sagas / total_sagas) * 100
  
# Saga P95 Duration
- Name: saga_p95_duration
  Target: <= 5 seconds
  Formula: 95th percentile of saga duration
  
# Retry Success Rate
- Name: retry_success_rate
  Target: >= 80%
  Formula: (successful_retries / total_retries) * 100
  
# DLQ Queue Size
- Name: dlq_queue_size
  Target: <= 100 messages
  Formula: count(dlq_messages where status=PENDING)
  
# Compensation Success Rate
- Name: compensation_success_rate
  Target: >= 99%
  Formula: (successful_compensations / total_compensations) * 100
```

---

### 8.2 SLOs (Service Level Objectives)

```yaml
# Availability
- Name: saga_availability
  Target: 99.5% uptime
  Window: 30 days
  
# Latency
- Name: saga_latency_p99
  Target: 99% of sagas complete in < 10 seconds
  Window: 1 hour
  
# Error Budget
- Name: saga_error_budget
  Target: 0.5% error rate (5 errors per 1000 requests)
  Window: 30 days
```

---

### 8.3 Alertas Sugeridos

```yaml
# Critical Alerts
- Name: saga_failure_spike
  Condition: saga_failure_rate > 10% for 5 minutes
  Severity: critical
  Notification: Email + PagerDuty
  
- Name: dlq_overflow
  Condition: dlq_queue_size > 500
  Severity: critical
  Notification: Email + Slack
  
# Warning Alerts
- Name: saga_slow_performance
  Condition: saga_p95_duration > 10 seconds for 15 minutes
  Severity: warning
  Notification: Slack
  
- Name: retry_rate_high
  Condition: saga_retry_rate > 30% for 10 minutes
  Severity: warning
  Notification: Slack
```

---

## 9. 🎯 ROADMAP DE IMPLEMENTAÇÃO

### Fase 1: Correções Críticas (Sprint 1 - 1 semana)
- ✅ Garantir idempotência completa (Step 1 e 2)
- ✅ Adicionar timeouts em steps
- ✅ Ativar DLQ worker no Celery Beat
- ✅ Testes de idempotência

**Deliverables:**
- PR com correções de idempotência
- Testes unitários para idempotência
- DLQ worker funcionando
- Documentação atualizada

---

### Fase 2: Resiliência (Sprint 2 - 2 semanas)
- ✅ Implementar circuit breakers globais
- ✅ Enriquecer Sentry integration
- ✅ Adicionar structured logging
- ✅ Testes de resiliência

**Deliverables:**
- Circuit breakers em todas external services
- Sentry com contexto rico e breadcrumbs
- Logs estruturados (JSON)
- Suite de testes de resiliência

---

### Fase 3: Observabilidade (Sprint 3 - 2 semanas)
- ✅ Implementar métricas Prometheus
- ✅ Dashboard Grafana
- ✅ Alertas configurados
- ✅ Runbooks para oncall

**Deliverables:**
- Métricas completas de saga
- Dashboard operacional
- Alert manager configurado
- Runbooks documentados

---

### Fase 4: Otimização (Sprint 4 - 1 semana)
- ✅ Otimizar retry delays baseado em dados
- ✅ Implementar adaptive retry
- ✅ Melhorar categorização de erros com ML
- ✅ Benchmarks de performance

**Deliverables:**
- Retry delays otimizados
- Sistema de retry adaptativo
- Classificador de erros com ML
- Relatório de benchmarks

---

## 10. 📚 REFERÊNCIAS

### Documentação Interna
- `app/coordination/saga_orchestrator.py` - Saga pattern implementation
- `app/tasks/saga_retry.py` - Retry mechanism
- `app/services/dlq_service.py` - Dead letter queue
- `app/domain/errors/flows/` - Error handling system
- `app/resilience/` - Resilience patterns

### Padrões e Práticas
- Saga Pattern: https://microservices.io/patterns/data/saga.html
- Circuit Breaker: https://martinfowler.com/bliki/CircuitBreaker.html
- Retry with Exponential Backoff: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
- Idempotency: https://stripe.com/blog/idempotency

### Ferramentas
- Celery: https://docs.celeryq.dev/
- Prometheus: https://prometheus.io/docs/
- Sentry: https://docs.sentry.io/
- Structlog: https://www.structlog.org/

---

## 11. 🏁 CONCLUSÃO

O sistema de tratamento de erros e compensações da saga está **bem fundamentado** com:
- ✅ 3 níveis de retry bem definidos
- ✅ Compensações automáticas em ordem reversa
- ✅ Classificação inteligente de erros
- ✅ DLQ implementada
- ✅ Sistema de alertas multi-nível

**Gaps principais a serem endereçados:**
1. **CRÍTICO:** Idempotência incompleta nos steps 1 e 2
2. **CRÍTICO:** DLQ worker não ativo
3. **ALTO:** Circuit breakers faltando em external services
4. **ALTO:** Sentry integration incompleta
5. **MÉDIO:** Falta de timeouts em steps

**Recomendação:** Implementar Fase 1 (correções críticas) imediatamente antes de promover para produção.

---

**Preparado por:** Claude Code  
**Data:** 2025-11-07  
**Versão:** 1.0  
