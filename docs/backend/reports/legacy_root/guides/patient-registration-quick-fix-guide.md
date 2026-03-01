# 🚨 PATIENT REGISTRATION - QUICK FIX GUIDE

**Para o relatório completo:** Ver `PATIENT_REGISTRATION_DEBUG_COMPLETE_REPORT.md`

---

## 🔥 BUGS CRÍTICOS (FIX IMEDIATO)

### 1. Perda de Dados Clínicos ao Criar Paciente

**Arquivo:** `app/api/v2/routers/patients/crud.py:375-387`

**Problema:** Campos clínicos (allergies, medications, blood_type, emergency_contact) são **perdidos** na conversão de `PatientV2Create` para `PatientCreate`.

**Fix:**
```python
# ANTES (❌ PERDE DADOS)
created = await coordinator.create_patient(
    patient_data=PatientCreate(
        phone=patient_data.phone,
        name=patient_data.name,
        # ... outros campos ...
        timezone=patient_data.timezone,
        # ❌ PERDIDOS: allergies, medications, blood_type, emergency_contact
    ),
    doctor_id=doctor_uuid,
    current_user=current_user,
    idempotency_key=x_idempotency_key,
)

# DEPOIS (✅ PRESERVA TODOS OS DADOS)
created = await coordinator.create_patient(
    patient_data=PatientCreate(
        phone=patient_data.phone,
        name=patient_data.name,
        email=patient_data.email,
        birth_date=patient_data.birth_date,
        cpf=patient_data.cpf,
        treatment_type=patient_data.treatment_type,
        treatment_start_date=patient_data.treatment_start_date,
        doctor_notes=patient_data.doctor_notes,
        diagnosis=patient_data.diagnosis,
        treatment_phase=patient_data.treatment_phase,
        timezone=patient_data.timezone,
        # ✅ INCLUIR CAMPOS CLÍNICOS NO METADATA
        metadata={
            "allergies": patient_data.allergies,
            "medications": patient_data.medications,
            "blood_type": patient_data.blood_type,
            "emergency_contact": patient_data.emergency_contact,
            **(patient_data.patient_data or {}),
        },
    ),
    doctor_id=doctor_uuid,
    current_user=current_user,
    idempotency_key=x_idempotency_key,
)
```

---

### 2. Validação de Telefone Inconsistente (Permite Duplicação)

**Arquivos:**
- `app/schemas/v2/patient.py:94-114`
- `app/orchestration/saga_orchestrator.py:108-112`

**Problema:** Telefone normalizado de formas diferentes em schema e saga, gerando hashes diferentes para o mesmo número.

**Exemplo de Falha:**
```python
# Request 1: "11987654321" → hash ABC123
# Request 2: "+5511987654321" → hash DEF456 (DIFERENTE!)
# Lock distribuído não detecta duplicação!
```

**Fix 1: Schema (Normalizar SEMPRE para E.164)**
```python
# app/schemas/v2/patient.py:94-114
@field_validator("phone")
@classmethod
def validate_phone_format(cls, v):
    from app.schemas.validators.phone import normalize_phone, PhoneValidationMode

    # ✅ SEMPRE normalizar para E.164 no schema
    return normalize_phone(v, mode=PhoneValidationMode.BR_TO_E164, allow_none=True)
    # Resultado: "11987654321" → "+5511987654321"
    #           "+5511987654321" → "+5511987654321"
```

**Fix 2: Saga (Usar mesma normalização)**
```python
# app/orchestration/saga_orchestrator.py:108-112
from app.schemas.validators.phone import normalize_phone, PhoneValidationMode

# ✅ Usar MESMA função de normalização do schema
normalized_phone = normalize_phone(
    patient_data.phone,
    mode=PhoneValidationMode.BR_TO_E164
)
phone_hash = hashlib.sha256(normalized_phone.encode()).hexdigest()[:32]
```

---

### 3. Saga Locks Longos (Risco de Deadlock)

**Arquivo:** `app/orchestration/saga_orchestrator.py:132-158`

**Problema:** Transação fica aberta por **até 60 segundos**, causando:
- Row locks em PostgreSQL
- Deadlocks em requests concorrentes
- Timeouts de transação

**Fix: Usar Savepoints**
```python
# app/orchestration/saga_orchestrator.py:138-158

try:
    # ✅ STEP 1: Create Patient (com savepoint)
    with self.db.begin_nested():  # SAVEPOINT sp1
        patient = await self._step_create_patient(
            saga, patient_data, doctor_id, idempotency_key
        )
        self.db.flush()

        saga.patient_id = patient.id
        saga.current_step = 1
        saga.status = SagaStatus.STEP_1_PATIENT_CREATED
        saga.add_log_entry(1, "create_patient", "success")
        # Commit do savepoint, locks liberados!

    # ✅ STEP 2: Initialize Flow (com savepoint)
    with self.db.begin_nested():  # SAVEPOINT sp2
        await self._step_initialize_flow(saga, patient, current_user)
        self.db.flush()

        saga.current_step = 3
        saga.status = SagaStatus.STEP_3_FLOW_INITIALIZED
        saga.add_log_entry(3, "initialize_flow", "success")
        # Commit do savepoint, locks liberados!

    # ✅ STEP 3: Send Welcome Message (com savepoint)
    with self.db.begin_nested():  # SAVEPOINT sp3
        await self._step_send_welcome_message(saga, patient)
        self.db.flush()

        saga.current_step = 4
        saga.status = SagaStatus.STEP_4_MESSAGE_SENT
        # Commit do savepoint, locks liberados!

    # Final commit (rápido, apenas saga status)
    saga.status = SagaStatus.COMPLETED
    saga.completed_at = now_sao_paulo()
    self.db.commit()

    return patient

except Exception as e:
    # Rollback até último savepoint que deu erro
    self.db.rollback()
    # ... compensação ...
```

---

## ⚠️ PROBLEMAS MÉDIOS (PRÓXIMA SPRINT)

### 4. Compensação pode Falhar Silenciosamente

**Arquivo:** `app/orchestration/saga_orchestrator.py:595-644`

**Problema:** Se compensação falhar após 3 retries, dados órfãos ficam no banco sem alerta.

**Fix: Adicionar Alertas Críticos**
```python
# Após todas as tentativas falharem
logger.critical(  # ✅ Mudar de ERROR para CRITICAL
    f"COMPENSATION FAILURE AFTER {max_retries} RETRIES",
    extra={
        "saga_id": str(saga.id),
        "step": step_num,
        "patient_id": str(saga.patient_id),
    }
)

# ✅ Enviar para Sentry
if settings.SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.capture_exception(
        SagaCompensationError(
            f"Saga {saga.id} compensation failed at step {step_num}",
            saga_id=saga.id,
        )
    )

# ✅ Marcar patient como quarentined
if saga.patient_id:
    patient = self.patient_repo.get_by_id(saga.patient_id)
    if patient:
        patient.patient_data["quarantine"] = {
            "reason": "saga_compensation_failed",
            "saga_id": str(saga.id),
            "timestamp": now_sao_paulo().isoformat(),
        }
        self.db.commit()
```

---

### 5. Falta Circuit Breaker para WhatsApp API

**Arquivo:** `app/orchestration/saga_orchestrator.py:410`

**Problema:** Se WhatsApp API estiver down, cada request demora 30s tentando enviar.

**Fix: Implementar Circuit Breaker**
```python
# app/utils/circuit_breaker.py (criar novo arquivo)
import time
from typing import Callable, Any

class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN."""
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e

    def on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

# Usar no saga_orchestrator.py
whatsapp_breaker = CircuitBreaker(failure_threshold=5, timeout=60)

try:
    success = whatsapp_breaker.call(
        self.whatsapp_service.send_message,
        message
    )
except CircuitBreakerOpenError:
    logger.warning("WhatsApp circuit breaker OPEN, skipping message")
    message.status = MessageStatus.PENDING
    # Tarefa de retry será executada depois
```

---

## 🧪 TESTES ESSENCIAIS

### Teste 1: Campos Clínicos Salvos
```python
@pytest.mark.asyncio
async def test_clinical_fields_saved():
    patient_data = PatientV2Create(
        name="João Silva",
        phone="11987654321",
        doctor_id=doctor.id,
        allergies="Penicilina",
        medications="Levotiroxina 100mcg",
        blood_type="A+",
        emergency_contact="Maria Silva - (11) 99999-9999",
    )

    response = await client.post("/api/v2/patients", json=patient_data.dict())
    assert response.status_code == 201

    # ✅ Verificar que campos clínicos foram salvos
    patient = response.json()
    assert patient.get("allergies") == "Penicilina"
    assert patient.get("medications") == "Levotiroxina 100mcg"
    assert patient.get("blood_type") == "A+"
```

### Teste 2: Telefone Normalizado Consistentemente
```python
@pytest.mark.asyncio
async def test_phone_normalization_consistent():
    """Diferentes formatos de telefone devem gerar mesmo hash."""

    phone_formats = [
        "11987654321",
        "(11) 98765-4321",
        "+5511987654321",
        "+55 11 98765-4321",
    ]

    for phone in phone_formats:
        patient_data = PatientV2Create(
            name=f"Test {phone}",
            phone=phone,
            doctor_id=doctor.id,
        )

        response = await client.post("/api/v2/patients", json=patient_data.dict())

        # ✅ Primeira criação: sucesso
        # ✅ Demais: 409 Conflict (duplicação detectada)
        if phone == phone_formats[0]:
            assert response.status_code == 201
        else:
            assert response.status_code == 409  # Duplicate detected
```

### Teste 3: Saga Compensa Corretamente
```python
@pytest.mark.asyncio
async def test_saga_compensates_on_failure(mocker):
    """Saga deve deletar patient se WhatsApp falhar."""

    # Mock WhatsApp para sempre falhar
    mocker.patch(
        'app.services.unified_whatsapp_service.UnifiedWhatsAppService.send_message',
        side_effect=Exception("WhatsApp API down")
    )

    patient_data = PatientV2Create(...)
    response = await client.post("/api/v2/patients", json=patient_data.dict())

    # ✅ Saga deve compensar
    assert response.status_code in [400, 500]

    # ✅ Patient NÃO deve existir no banco
    db_patient = db.query(Patient).filter(
        Patient.phone_hash == compute_phone_hash(patient_data.phone)
    ).first()
    assert db_patient is None
```

---

## 📋 CHECKLIST PRÉ-DEPLOY

Antes de fazer deploy das correções:

### Funcional
- [ ] Teste manual: criar paciente com todos os campos clínicos
- [ ] Verificar no banco: `allergies`, `medications`, `blood_type` salvos em `patient_data`
- [ ] Criar 2 pacientes com telefones em formatos diferentes (deve detectar duplicação)
- [ ] Forçar falha de WhatsApp (mock): verificar compensação deletou patient

### Performance
- [ ] Medir tempo de transação: deve ser < 5s com savepoints
- [ ] Verificar locks no PostgreSQL: `SELECT * FROM pg_locks WHERE granted = false;`
- [ ] Testar concorrência: 10 requests simultâneos, apenas 1 deve ter sucesso

### Segurança
- [ ] Logs não expõem PII (telefone, email, CPF em plaintext)
- [ ] Sentry configurado com `scrubbing_fields`
- [ ] Dados encriptados corretamente em `phone_encrypted`, `email_encrypted`, `cpf_encrypted`

### Monitoramento
- [ ] Métricas Prometheus configuradas (`patient_creation_total`, `saga_step_duration`)
- [ ] Alertas configurados no Sentry para `SagaCompensationError`
- [ ] Dashboard com latência P50, P95, P99 de criação de paciente

---

## 🚀 ORDEM DE IMPLEMENTAÇÃO

### Sprint Atual (Esta Semana)
1. **Dia 1-2:** Fix #1 (Perda de dados clínicos) ← CRÍTICO
2. **Dia 2-3:** Fix #2 (Normalização de telefone) ← CRÍTICO
3. **Dia 3-4:** Fix #3 (Savepoints no saga) ← ALTO
4. **Dia 4-5:** Testes de integração

### Próxima Sprint
5. **Fix #4:** Alertas de compensação
6. **Fix #5:** Circuit breaker WhatsApp
7. **Refatoração:** Extrair validadores compartilhados
8. **Monitoramento:** Dashboards e alertas

---

## 📞 SUPORTE

**Relatório completo:** `docs/PATIENT_REGISTRATION_DEBUG_COMPLETE_REPORT.md`

**Dúvidas:**
- GitHub Issues com tag `[patient-registration]`
- Code review: Backend team
- Arquitetura: Tech lead

**Data:** 2025-12-24
**Branch:** docs-refactor-py313

---

**FIM DO GUIA RÁPIDO**
