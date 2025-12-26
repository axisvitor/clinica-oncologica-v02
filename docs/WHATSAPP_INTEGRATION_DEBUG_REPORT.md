# 🔍 DEBUG COMPLETO - INTEGRAÇÃO WHATSAPP
**Sistema:** Clínica Oncológica v02-1
**Data:** 2025-12-24
**Análise:** Integração Evolution API para Acompanhamento Diário de Pacientes

---

## 📋 SUMÁRIO EXECUTIVO

### ✅ Pontos Fortes Identificados
- ✅ Arquitetura modular bem estruturada (Evolution API + WhatsApp Service)
- ✅ Retry logic implementado com backoff exponencial
- ✅ Idempotência de mensagens (Redis + Database)
- ✅ Webhook handlers com proteção contra duplicação
- ✅ Rate limiting configurado (500 req/min)
- ✅ Validação de assinatura HMAC para webhooks

### 🔴 BUGS CRÍTICOS IDENTIFICADOS

#### 🚨 **BUG #1: Inicialização Assíncrona do Evolution Client**
**Arquivo:** `/backend-hormonia/app/integrations/evolution/client.py:309-320`
**Severidade:** CRÍTICA

```python
# PROBLEMA: get_evolution_client() retorna instância NÃO inicializada
_evolution_client: Optional[EvolutionClient] = None

async def get_evolution_client() -> EvolutionClient:
    global _evolution_client
    if _evolution_client is None:
        _evolution_client = EvolutionClient()  # ❌ Construtor síncrono
    return _evolution_client
```

**Impacto:**
- Cliente HTTP não inicializado corretamente
- Conexões podem falhar silenciosamente
- Memory leaks em conexões não fechadas

**Correção Recomendada:**
```python
_evolution_client: Optional[EvolutionClient] = None
_client_lock = asyncio.Lock()

async def get_evolution_client() -> EvolutionClient:
    global _evolution_client

    async with _client_lock:
        if _evolution_client is None:
            _evolution_client = EvolutionClient()
            # Ensure client is ready
            await _evolution_client.__aenter__()

    return _evolution_client
```

---

#### 🚨 **BUG #2: Race Condition no Webhook Idempotency**
**Arquivo:** `/backend-hormonia/app/integrations/whatsapp/api/webhooks.py:55-95`
**Severidade:** ALTA

```python
# PROBLEMA: Verificação não-atômica entre check e set
async def is_event_processed(event_id: str, event_type: str = "webhook") -> bool:
    idempotency = await get_idempotency_service()

    # ❌ Race condition: Entre acquire e return outro worker pode processar
    acquired, reason = await idempotency.try_acquire(
        event_type=event_type, event_id=event_id
    )

    if not acquired:
        return True  # Already processed

    return False  # New event - PROBLEMA: outro worker pode ver "new" também
```

**Impacto:**
- Mensagens duplicadas podem ser processadas
- Pacientes podem receber mensagens duplicadas
- Dados inconsistentes no banco

**Correção Recomendada:**
```python
async def is_event_processed(event_id: str, event_type: str = "webhook") -> bool:
    try:
        idempotency = await get_idempotency_service()

        # Atomic SET NX EX - only one worker will succeed
        acquired, reason = await idempotency.try_acquire(
            event_type=event_type,
            event_id=event_id
        )

        # If we acquired the lock, this is a NEW event (not processed)
        # If we didn't acquire, it's already being processed
        return not acquired  # Inverted: True = already processed

    except Exception as e:
        logger.error(f"Idempotency check failed: {e}")
        # Fallback to legacy method with proper atomic SET NX
        return await _legacy_atomic_check(event_id)
```

---

#### 🚨 **BUG #3: WhatsApp Service Usa Cliente Não-Await**
**Arquivo:** `/backend-hormonia/app/domain/messaging/whatsapp/whatsapp_service.py:119-120`
**Severidade:** CRÍTICA

```python
def __init__(self, db: Session, messaging_mode: MessagingMode = MessagingMode.QUEUE, redis: Optional[Redis] = None):
    # ...
    # ❌ PROBLEMA: get_evolution_client() é async mas não é await
    self.evolution_client = get_evolution_client()
```

**Impacto:**
- `self.evolution_client` é um `coroutine`, NÃO um `EvolutionClient`
- Todas as chamadas subsequentes falham com `TypeError: object coroutine is not callable`
- Envio de mensagens completamente quebrado

**Correção Recomendada:**
```python
def __init__(
    self,
    db: Session,
    messaging_mode: MessagingMode = MessagingMode.QUEUE,
    redis: Optional[Redis] = None,
    evolution_client: Optional[EvolutionClient] = None  # Inject dependency
):
    self.db = db
    self.messaging_mode = messaging_mode
    self.redis = redis

    # Inject pre-initialized client
    self.evolution_client = evolution_client

    # Initialize repositories
    self.message_repo = MessageRepository(db)
    self.patient_repo = PatientRepository(db)

    # ...rest of init

# Factory function
async def get_whatsapp_service(db: Session, redis: Optional[Redis] = None) -> WhatsAppService:
    evolution_client = await get_evolution_client()  # ✅ Properly await
    return WhatsAppService(
        db=db,
        redis=redis,
        evolution_client=evolution_client
    )
```

---

#### 🚨 **BUG #4: Webhook Handler Missing Database Session Management**
**Arquivo:** `/backend-hormonia/app/integrations/whatsapp/api/webhooks.py:181-219`
**Severidade:** ALTA

```python
async def process_webhook_event(
    webhook_data: WebhookPayload,
    background_tasks: BackgroundTasks,
    db  # ❌ No type hint - pode ser Session ou None
):
    # ...
    try:
        if event == "messages.upsert":
            await handle_message_upsert(instance_name, data, background_tasks, db)
        # ...
    except Exception as e:
        logger.error("Error in webhook event processing", ...)
        # ❌ Sem rollback! Database transaction pode ficar pendente
```

**Impacto:**
- Transações de banco não finalizadas (commit/rollback)
- Conexões de banco vazam
- Deadlocks em alta concorrência

**Correção Recomendada:**
```python
async def process_webhook_event(
    webhook_data: WebhookPayload,
    background_tasks: BackgroundTasks,
    db: Session
):
    event = webhook_data.event.lower().replace("_", ".")
    data = webhook_data.data
    instance_name = webhook_data.instance

    try:
        # Route to appropriate handler
        if event == "messages.upsert":
            await handle_message_upsert(instance_name, data, background_tasks, db)
        # ... other handlers

        # ✅ Commit successful webhook processing
        db.commit()

    except Exception as e:
        # ✅ Rollback on error
        db.rollback()
        logger.error(
            "Error in webhook event processing",
            exc_info=True,
            extra={
                "event_type": event,
                "instance_name": instance_name,
                "error_type": type(e).__name__,
            }
        )
        raise  # Re-raise to return 500 to Evolution API
```

---

#### ⚠️ **BUG #5: Flow Engine Trigger em Thread Sem Gestão de Exceções**
**Arquivo:** `/backend-hormonia/app/integrations/whatsapp/api/webhooks.py:348-396`
**Severidade:** MÉDIA

```python
async def _trigger_flow_response_async(patient_id: str, content: str):
    import asyncio
    from app.database import get_scoped_session
    from app.services.enhanced_flow_engine import get_enhanced_flow_engine

    def _run_hybrid_flow():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            with get_scoped_session() as sync_db:
                engine = get_enhanced_flow_engine(sync_db)
                loop.run_until_complete(
                    engine.process_patient_response(patient_id, content)
                )

            loop.close()  # ❌ loop.close() em try - pode não executar se exception

        except Exception as e:
            logger.error(f"Error in background flow thread: {e}", exc_info=True)
            try:
                loop.close()  # ❌ loop pode não estar definido se erro antes
            except Exception as close_err:
                logger.debug(f"Event loop close error: {close_err}")
```

**Impacto:**
- Event loops podem vazar memória
- Respostas automáticas do flow podem não ser enviadas
- Pacientes não recebem follow-up esperado

**Correção Recomendada:**
```python
async def _trigger_flow_response_async(patient_id: str, content: str):
    import asyncio
    from app.database import get_scoped_session
    from app.services.enhanced_flow_engine import get_enhanced_flow_engine

    logger.info(f"Starting background flow processing for patient {patient_id}")

    def _run_hybrid_flow():
        loop = None  # ✅ Declare outside try
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            with get_scoped_session() as sync_db:
                engine = get_enhanced_flow_engine(sync_db)
                loop.run_until_complete(
                    engine.process_patient_response(patient_id, content)
                )

            logger.info(f"Completed flow processing for patient {patient_id}")

        except Exception as e:
            logger.error(
                f"Error in background flow thread for patient {patient_id}: {e}",
                exc_info=True
            )
        finally:
            # ✅ Always close loop
            if loop is not None:
                try:
                    loop.close()
                except Exception as close_err:
                    logger.debug(f"Event loop close error (non-critical): {close_err}")

    # Run in executor
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _run_hybrid_flow)
    except Exception as e:
        logger.error(f"Failed to schedule background flow task: {e}", exc_info=True)
```

---

## 🔄 FLUXO DE MENSAGENS WHATSAPP

### 📤 ENVIO DE MENSAGENS (Outbound)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Application Layer                                            │
│    └─> WhatsAppService.send_message_to_patient()               │
│        • Cria Message com status PENDING                        │
│        • Adiciona ao banco de dados                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Service Layer                                                │
│    └─> WhatsAppService.send_message()                          │
│        • Valida paciente existe                                 │
│        • Formata número de telefone (55 + number)               │
│        • Chama Evolution API                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Evolution Client                                             │
│    └─> EvolutionClient.send_text_message()                     │
│        • Rate limiting (check quota)                            │
│        • HTTP POST /message/sendText/{instance}                 │
│        • Retry on failure (max 3x, exponential backoff)         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Evolution API (External Service)                             │
│    • Processa mensagem                                          │
│    • Envia via WhatsApp Business API                            │
│    • Retorna message_id                                         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Database Update                                              │
│    • status = SENT                                              │
│    • whatsapp_id = message_id                                   │
│    • sent_at = timestamp                                        │
│    • WebSocket broadcast (MESSAGE_SENT event)                   │
└─────────────────────────────────────────────────────────────────┘
```

**🔴 PROBLEMAS NO FLUXO DE ENVIO:**
1. ❌ Evolution Client não é await corretamente (BUG #3)
2. ❌ Retry logic pode gerar mensagens duplicadas (sem idempotency key)
3. ⚠️ Falta circuit breaker para falhas consecutivas

---

### 📥 RECEBIMENTO DE MENSAGENS (Inbound via Webhook)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Evolution API                                                │
│    • Recebe mensagem do paciente via WhatsApp                   │
│    • POST /webhooks/whatsapp/evolution/{instance_name}          │
│    • Payload: { event: "messages.upsert", data: {...} }         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Webhook Endpoint (FastAPI)                                   │
│    └─> evolution_webhook()                                      │
│        • Rate limit: 500/min por IP+instance                    │
│        • Valida WebhookPayload                                  │
│        • Chama process_webhook_event()                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Event Processing                                             │
│    └─> process_webhook_event()                                  │
│        • Normaliza event name                                   │
│        • Roteia para handler específico                         │
│        • messages.upsert → handle_message_upsert()              │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Message Handler                                              │
│    └─> handle_message_upsert()                                  │
│        • Extrai message_id, chat_id, sender_id                  │
│        • ✅ Idempotency check (is_event_processed)              │
│        • Determina tipo (text/image/audio/video)                │
│        • Cria WhatsAppMessage (status=DELIVERED)                │
│        • Salva no banco de dados                                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Patient Lookup & Flow Trigger                                │
│    • Busca Patient por phone_hash (LGPD compliant)              │
│    • Se paciente encontrado:                                    │
│      └─> background_tasks.add_task(                             │
│            _trigger_flow_response_async, patient_id, content    │
│          )                                                       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. Flow Engine Processing (Background Task)                     │
│    └─> _trigger_flow_response_async()                          │
│        • Cria novo event loop em thread separado                │
│        • Executa flow engine com sync DB session                │
│        • Processa resposta do paciente                          │
│        • Pode enviar mensagens de follow-up                     │
└─────────────────────────────────────────────────────────────────┘
```

**🔴 PROBLEMAS NO FLUXO DE RECEBIMENTO:**
1. ❌ Race condition no idempotency check (BUG #2)
2. ❌ Database session sem commit/rollback (BUG #4)
3. ❌ Event loop pode vazar em background task (BUG #5)
4. ⚠️ Sem validação de assinatura HMAC (opcional mas recomendado)

---

## 📊 ANÁLISE DE COMPONENTES

### 1️⃣ Evolution API Client
**Arquivo:** `/backend-hormonia/app/integrations/evolution/client.py`

**✅ Pontos Fortes:**
- Arquitetura modular (client, request_handler, message_sender, webhook_handler)
- Rate limiting implementado
- Retry com exponential backoff
- Mock mode para testes
- Logging estruturado com structlog

**🔴 Problemas:**
```python
# LINHA 309-320: Global client sem inicialização assíncrona
async def get_evolution_client() -> EvolutionClient:
    global _evolution_client
    if _evolution_client is None:
        _evolution_client = EvolutionClient()  # ❌ Não await
    return _evolution_client
```

**Configuração:**
```python
# Settings esperadas
WHATSAPP_EVOLUTION_API_URL = "http://localhost:8080"
WHATSAPP_EVOLUTION_INSTANCE_NAME = "clinica_oncologica"
WHATSAPP_EVOLUTION_API_KEY = "your-api-key"
WHATSAPP_EVOLUTION_WEBHOOK_SECRET = None  # ⚠️ Opcional mas recomendado
```

---

### 2️⃣ WhatsApp Service
**Arquivo:** `/backend-hormonia/app/domain/messaging/whatsapp/whatsapp_service.py`

**✅ Funcionalidades:**
- Envio de mensagens (texto, imagem, botões)
- Retry policies configuráveis
- Idempotência via `IdempotentMessageSender`
- WebSocket notifications
- Flow callbacks

**🔴 CRITICAL BUG (LINHA 119-120):**
```python
def __init__(self, db: Session, ...):
    # ...
    self.evolution_client = get_evolution_client()  # ❌ Não await!
    # Este é um coroutine, não um EvolutionClient!
```

**Impacto:**
- Todas as chamadas a `self.evolution_client.send_text_message()` falham
- `TypeError: 'coroutine' object is not callable`

**Retry Policies:**
```python
{
    "default": {
        "max_retries": 3,
        "backoff_factor": 2,
        "base_delay": 300  # 5 minutes
    },
    "flow_message": {
        "max_retries": 5,
        "backoff_factor": 1.5,
        "base_delay": 180  # 3 minutes
    }
}
```

---

### 3️⃣ Webhook Handler
**Arquivo:** `/backend-hormonia/app/integrations/whatsapp/api/webhooks.py`

**✅ Features:**
- Rate limiting: 500 req/min por IP+instance
- Atomic idempotency com Redis SET NX EX
- Background task processing
- Suporte a múltiplos tipos de evento

**🔴 Problemas Identificados:**

#### A) Idempotency Race Condition (LINHA 55-95)
```python
async def is_event_processed(event_id: str, event_type: str = "webhook") -> bool:
    idempotency = await get_idempotency_service()
    acquired, reason = await idempotency.try_acquire(...)

    if not acquired:
        return True  # Already processed

    return False  # ❌ PROBLEMA: Lógica invertida!
```

**Lógica Correta:**
- `acquired = True` → Lock foi adquirido → Evento é NOVO → return `False` (não processado)
- `acquired = False` → Lock não adquirido → Evento JÁ PROCESSADO → return `True`

#### B) Database Transaction Management (LINHA 181-219)
```python
async def process_webhook_event(webhook_data, background_tasks, db):
    try:
        # Process events...
        if event == "messages.upsert":
            await handle_message_upsert(...)
    except Exception as e:
        logger.error(...)
        # ❌ Sem db.rollback()!
```

**Consequências:**
- Transações pendentes no pool de conexões
- Deadlocks em alta carga
- Dados inconsistentes

---

### 4️⃣ Message Models
**Arquivo:** `/backend-hormonia/app/integrations/whatsapp/models/message.py`

**Modelos Principais:**
```python
class WebhookPayload(BaseModel):
    instance: str
    data: Dict[str, Any]
    event: str

class WhatsAppMessage:
    id: str
    instance_name: str
    chat_id: str
    sender_id: str
    recipient_id: str
    message_type: str
    content: str
    status: MessageStatus  # PENDING, SENT, DELIVERED, READ
    external_id: str  # Evolution API message ID
    created_at: datetime
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]
```

**✅ Bem estruturado, sem problemas críticos**

---

## 🛠️ RECOMENDAÇÕES DE CORREÇÃO

### 🔥 PRIORIDADE CRÍTICA (P0)

#### 1. Corrigir Evolution Client Initialization
**Arquivo:** `/backend-hormonia/app/integrations/evolution/client.py`

```python
# ANTES (ERRADO):
async def get_evolution_client() -> EvolutionClient:
    global _evolution_client
    if _evolution_client is None:
        _evolution_client = EvolutionClient()
    return _evolution_client

# DEPOIS (CORRETO):
_evolution_client: Optional[EvolutionClient] = None
_client_lock = asyncio.Lock()

async def get_evolution_client() -> EvolutionClient:
    global _evolution_client

    async with _client_lock:
        if _evolution_client is None:
            _evolution_client = EvolutionClient()
            # Initialize HTTP client properly
            await _evolution_client.__aenter__()

    return _evolution_client

# Lifespan event
async def close_evolution_client():
    global _evolution_client
    if _evolution_client:
        await _evolution_client.__aexit__(None, None, None)
        _evolution_client = None
```

---

#### 2. Corrigir WhatsApp Service Dependency Injection
**Arquivo:** `/backend-hormonia/app/domain/messaging/whatsapp/whatsapp_service.py`

```python
# ANTES (ERRADO):
class WhatsAppService:
    def __init__(self, db: Session, ...):
        self.evolution_client = get_evolution_client()  # ❌ Não await

# DEPOIS (CORRETO):
class WhatsAppService:
    def __init__(
        self,
        db: Session,
        messaging_mode: MessagingMode = MessagingMode.QUEUE,
        redis: Optional[Redis] = None,
        evolution_client: Optional[EvolutionClient] = None  # ✅ Inject
    ):
        self.db = db
        self.messaging_mode = messaging_mode
        self.redis = redis
        self.evolution_client = evolution_client  # ✅ Use injected

        # ... rest of init

# Factory function
async def get_whatsapp_service(
    db: Session,
    redis: Optional[Redis] = None
) -> WhatsAppService:
    evolution_client = await get_evolution_client()  # ✅ Properly await
    return WhatsAppService(
        db=db,
        redis=redis,
        evolution_client=evolution_client
    )
```

---

#### 3. Corrigir Webhook Idempotency Logic
**Arquivo:** `/backend-hormonia/app/integrations/whatsapp/api/webhooks.py`

```python
# ANTES (ERRADO):
async def is_event_processed(event_id: str, event_type: str) -> bool:
    acquired, reason = await idempotency.try_acquire(...)
    if not acquired:
        return True  # Already processed
    return False  # New event ❌ LÓGICA INVERTIDA

# DEPOIS (CORRETO):
async def is_event_processed(event_id: str, event_type: str) -> bool:
    try:
        idempotency = await get_idempotency_service()

        # Atomic SET NX EX - only one worker will succeed
        acquired, reason = await idempotency.try_acquire(
            event_type=event_type,
            event_id=event_id
        )

        # ✅ CORRECT LOGIC:
        # acquired = True  → Lock acquired → NEW event → return False
        # acquired = False → Lock NOT acquired → ALREADY PROCESSED → return True

        if acquired:
            logger.debug(f"New webhook event acquired: {event_id}")
            return False  # New event - NOT processed yet
        else:
            logger.info(
                f"Duplicate webhook event ignored: {event_id}",
                extra={"event_id": event_id, "reason": reason}
            )
            return True  # Already processed

    except Exception as e:
        logger.error(f"Idempotency check failed: {e}", exc_info=True)
        # Fallback to fail-open (process event) to avoid data loss
        return False
```

---

#### 4. Adicionar Database Transaction Management
**Arquivo:** `/backend-hormonia/app/integrations/whatsapp/api/webhooks.py`

```python
# ANTES (ERRADO):
async def process_webhook_event(webhook_data, background_tasks, db):
    try:
        if event == "messages.upsert":
            await handle_message_upsert(...)
    except Exception as e:
        logger.error(...)
        # ❌ Sem rollback

# DEPOIS (CORRETO):
async def process_webhook_event(
    webhook_data: WebhookPayload,
    background_tasks: BackgroundTasks,
    db: Session  # ✅ Type hint
):
    event = webhook_data.event.lower().replace("_", ".")

    try:
        # Route to appropriate handler
        if event == "messages.upsert":
            await handle_message_upsert(instance_name, data, background_tasks, db)
        elif event == "messages.update":
            await handle_message_update(instance_name, data, db)
        # ... other handlers

        # ✅ COMMIT on success
        db.commit()
        logger.info(f"Webhook event processed successfully: {event}")

    except Exception as e:
        # ✅ ROLLBACK on error
        db.rollback()
        logger.error(
            "Webhook processing failed",
            exc_info=True,
            extra={
                "event_type": event,
                "instance_name": webhook_data.instance,
                "error": str(e)
            }
        )
        raise  # Re-raise to return 500 to Evolution API
```

---

### ⚠️ PRIORIDADE ALTA (P1)

#### 5. Adicionar Circuit Breaker para Evolution API
**Novo arquivo:** `/backend-hormonia/app/integrations/evolution/circuit_breaker.py`

```python
from enum import Enum
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Too many failures, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

class EvolutionCircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_attempts: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout_seconds)
        self.half_open_attempts = half_open_attempts

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.success_count = 0

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            # Check if timeout elapsed
            if datetime.now() - self.last_failure_time > self.timeout:
                logger.info("Circuit breaker entering HALF_OPEN state")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise Exception("Circuit breaker OPEN - Evolution API unavailable")

        try:
            result = await func(*args, **kwargs)

            # Success - reset counters
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.half_open_attempts:
                    logger.info("Circuit breaker CLOSED - service recovered")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.failure_count >= self.failure_threshold:
                logger.error(f"Circuit breaker OPEN - {self.failure_count} failures")
                self.state = CircuitState.OPEN

            raise
```

---

#### 6. Adicionar HMAC Signature Validation nos Webhooks
**Arquivo:** `/backend-hormonia/app/integrations/whatsapp/api/webhooks.py`

```python
@router.post("/evolution/{instance_name}")
@limiter.limit("500/minute", key_func=_webhook_rate_limit_key)
async def evolution_webhook(
    instance_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        # Get raw payload and signature
        raw_payload = await request.body()
        signature = request.headers.get("X-Signature") or request.headers.get("X-Hub-Signature-256")

        # ✅ VALIDATE SIGNATURE (if configured)
        if settings.WHATSAPP_EVOLUTION_WEBHOOK_SECRET:
            evolution_client = await get_evolution_client()
            is_valid = evolution_client.validate_webhook_signature(
                payload=raw_payload,
                signature=signature
            )

            if not is_valid:
                logger.warning(
                    "Invalid webhook signature detected",
                    extra={"instance": instance_name, "ip": request.client.host}
                )
                raise HTTPException(
                    status_code=401,
                    detail="Invalid webhook signature"
                )

        # Parse payload
        payload = await request.json()

        # ... rest of processing
```

---

## 📝 CHECKLIST DE CORREÇÃO

### Fase 1: Correções Críticas (Implementar IMEDIATAMENTE)
- [ ] **BUG #3**: Corrigir `WhatsAppService.__init__()` para usar dependency injection
- [ ] **BUG #1**: Implementar `get_evolution_client()` com async/await correto
- [ ] **BUG #2**: Corrigir lógica invertida em `is_event_processed()`
- [ ] **BUG #4**: Adicionar `db.commit()` e `db.rollback()` em webhook handlers
- [ ] Testar envio de mensagem end-to-end

### Fase 2: Melhorias de Robustez
- [ ] **BUG #5**: Corrigir event loop leak em `_trigger_flow_response_async()`
- [ ] Adicionar Circuit Breaker para Evolution API
- [ ] Implementar HMAC signature validation
- [ ] Adicionar health check endpoint para Evolution API
- [ ] Configurar alertas para falhas consecutivas

### Fase 3: Testes
- [ ] Teste unitário: `WhatsAppService.send_message()`
- [ ] Teste integração: Evolution API mock
- [ ] Teste webhook: Idempotency com múltiplos workers
- [ ] Teste race condition: Mensagens duplicadas
- [ ] Teste circuit breaker: Recovery após falhas

---

## 🚀 PLANO DE IMPLEMENTAÇÃO

### Semana 1: Correções Críticas
**Dia 1-2:**
- Corrigir BUG #1, #3 (Evolution Client + WhatsApp Service)
- Atualizar todos os pontos de uso do `WhatsAppService`

**Dia 3-4:**
- Corrigir BUG #2, #4 (Webhook idempotency + transactions)
- Testar webhooks com carga

**Dia 5:**
- Corrigir BUG #5 (Event loop leak)
- Code review e testes

### Semana 2: Melhorias
**Dia 1-3:**
- Implementar Circuit Breaker
- Adicionar HMAC validation
- Configurar monitoring

**Dia 4-5:**
- Testes end-to-end
- Documentação atualizada
- Deploy em staging

---

## 📈 MÉTRICAS DE SUCESSO

### KPIs de Integração WhatsApp
1. **Taxa de Entrega:** > 99%
2. **Latência de Envio:** < 2s (p95)
3. **Taxa de Duplicação:** < 0.1%
4. **Disponibilidade:** > 99.9%
5. **Taxa de Erro:** < 1%

### Monitoring Recomendado
```python
# Prometheus metrics
whatsapp_messages_sent_total = Counter(...)
whatsapp_messages_failed_total = Counter(...)
whatsapp_delivery_latency_seconds = Histogram(...)
whatsapp_webhook_events_total = Counter(...)
whatsapp_duplicate_events_total = Counter(...)
evolution_api_circuit_breaker_state = Gauge(...)
```

---

## 🔗 REFERÊNCIAS

### Arquivos Críticos
1. `/backend-hormonia/app/integrations/evolution/client.py` - Evolution API Client
2. `/backend-hormonia/app/domain/messaging/whatsapp/whatsapp_service.py` - WhatsApp Service
3. `/backend-hormonia/app/integrations/whatsapp/api/webhooks.py` - Webhook Handlers
4. `/backend-hormonia/app/config/settings/integrations.py` - Configuração

### Documentação Externa
- [Evolution API Docs](https://doc.evolution-api.com/)
- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)

---

**Relatório gerado em:** 2025-12-24
**Próxima revisão:** Após implementação das correções críticas
