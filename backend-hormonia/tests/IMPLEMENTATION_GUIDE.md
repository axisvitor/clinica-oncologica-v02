# Guia de Implementação - Serviços Faltantes

## 📋 Overview

Os testes foram criados seguindo TDD (Test-Driven Development). Agora é necessário implementar os serviços reais que passarão nos testes.

## 🎯 Serviços a Implementar

### 1. EncryptionService
**Arquivo**: `app/services/encryption_service.py`

**Responsabilidades**:
- Criptografar/descriptografar CPF, email e telefone
- Gerar hashes SHA-256 para busca
- Validar formatos de entrada
- Normalizar dados antes de processar

**Interface Esperada**:
```python
class EncryptionService:
    def encrypt_cpf(self, cpf: str) -> Tuple[bytes, str]:
        """Encrypt CPF and return (encrypted_data, hash)"""

    def decrypt_cpf(self, encrypted: bytes) -> str:
        """Decrypt CPF from encrypted bytes"""

    def encrypt_email(self, email: str) -> Tuple[bytes, str]:
        """Encrypt email and return (encrypted_data, hash)"""

    def decrypt_email(self, encrypted: bytes) -> str:
        """Decrypt email from encrypted bytes"""

    def encrypt_phone(self, phone: str) -> Tuple[bytes, str]:
        """Encrypt phone and return (encrypted_data, hash)"""

    def decrypt_phone(self, encrypted: bytes) -> str:
        """Decrypt phone from encrypted bytes"""
```

**Implementação Sugerida**:
- Use `cryptography.fernet` para encryption
- Use `hashlib.sha256` para hashes
- Normalize CPF: apenas dígitos
- Normalize Email: lowercase
- Normalize Phone: apenas dígitos

**Testes**: `tests/services/test_encryption_lgpd.py` (25 casos)

---

### 2. IdempotencyService
**Arquivo**: `app/services/idempotency_service.py`

**Responsabilidades**:
- Cachear resultados de operações por chave
- Gerenciar TTL de chaves
- Verificar duplicatas
- Gerar chaves de idempotência

**Interface Esperada**:
```python
class IdempotencyService:
    def __init__(self, redis: Redis, default_ttl: int = 3600):
        self.redis = redis
        self.default_ttl = default_ttl

    async def cache_result(
        self,
        key: str,
        result: dict,
        ttl: Optional[int] = None
    ) -> None:
        """Cache operation result with TTL"""

    async def get_cached_result(self, key: str) -> Optional[dict]:
        """Retrieve cached result by key"""

    def generate_key(
        self,
        method: str,
        path: str,
        body: dict
    ) -> str:
        """Generate deterministic key from request"""
```

**Implementação Sugerida**:
- Use Redis com TTL
- Serialize com `json.dumps`
- Hash para gerar chave: `sha256(method + path + json.dumps(body))`

**Testes**: `tests/api/v2/test_idempotency.py` (18 casos)

---

### 3. WebhookService
**Arquivo**: `app/services/webhook_service.py`

**Responsabilidades**:
- Detectar eventos duplicados
- Marcar eventos como processados
- Gerenciar TTL de eventos

**Interface Esperada**:
```python
class WebhookService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def is_event_processed(self, event_id: str) -> bool:
        """Check if event was already processed"""

    async def mark_event_processed(
        self,
        event_id: str,
        ttl: int = 86400
    ) -> None:
        """Mark event as processed with TTL (default 24h)"""
```

**Implementação Sugerida**:
- Use Redis SET com TTL
- Key format: `webhook:event:{event_id}`
- TTL padrão: 24 horas

**Testes**: `tests/api/v2/test_idempotency.py` (4 casos)

---

### 4. SagaOrchestrator
**Arquivo**: `app/orchestration/saga_orchestrator.py`

**Responsabilidades**:
- Executar saga steps sequencialmente
- Executar compensação em caso de falha
- Persistir estado da saga
- Criar audit trail
- Coletar métricas

**Interface Esperada**:
```python
class SagaOrchestrator:
    def __init__(self, redis: Optional[Redis] = None):
        self.redis = redis
        self._steps: List[Tuple[Callable, Optional[Callable]]] = []
        self._metrics: List[dict] = []
        self._logger = logging.getLogger(__name__)

    async def execute_saga(self, context: dict) -> dict:
        """Execute all saga steps with compensation on failure"""

    async def execute_with_retry(
        self,
        step: Callable,
        context: dict,
        max_retries: int = 3
    ) -> dict:
        """Execute step with retry logic"""

    async def recover_saga(self, saga_id: str) -> dict:
        """Recover saga from persisted state"""

    async def _track_compensation_failure(
        self,
        saga_id: str,
        step: int,
        error: Exception
    ) -> None:
        """Track compensation failures in Redis"""

    async def _persist_saga_state(
        self,
        saga_id: str,
        state: dict
    ) -> None:
        """Persist saga state to Redis"""

    async def _log_step_execution(
        self,
        step_name: str,
        context: dict,
        success: bool
    ) -> None:
        """Log step execution"""

    async def _append_audit_trail(
        self,
        saga_id: str,
        audit_entry: dict
    ) -> None:
        """Append entry to audit trail"""
```

**Implementação Sugerida**:
- Pattern: List of (step, compensation) tuples
- Execute compensation in reverse order
- Use Redis para state e audit trail
- Timeout com `asyncio.wait_for`

**Testes**: `tests/services/test_saga_compensation.py` (15 casos)

---

### 5. LGPDMiddleware
**Arquivo**: `app/middleware/lgpd_middleware.py`

**Responsabilidades**:
- Logar acesso a dados sensíveis
- Validar consentimento
- Marcar dados para anonimização em exports

**Interface Esperada**:
```python
class LGPDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Log patient data access"""

    def _should_anonymize(self, request: Request) -> bool:
        """Check if data should be anonymized"""
```

**Implementação Sugerida**:
- Log em formato JSON
- Incluir: user_id, patient_id, action, timestamp, IP
- Paths sensíveis: `/patients/*`, `/medical-records/*`

**Testes**: `tests/middleware/test_lgpd_middleware.py` (4 casos)

---

### 6. PatientRepository (extensões)
**Arquivo**: `app/repositories/patient.py`

**Novas Responsabilidades**:
- Soft delete e hard delete
- Busca por hash
- Suporte a encryption

**Métodos Adicionais**:
```python
class PatientRepository(BaseRepository):
    async def soft_delete(self, patient_id: str) -> bool:
        """Soft delete - mark as deleted"""

    async def hard_delete(
        self,
        patient_id: str,
        audit_reason: str
    ) -> bool:
        """Hard delete - remove from database"""

    async def find_by_cpf_hash(self, cpf_hash: str) -> Optional[dict]:
        """Find patient by CPF hash"""

    async def get_full_data(self, patient_id: str) -> dict:
        """Get all patient data for export"""
```

**Testes**: `tests/middleware/test_lgpd_middleware.py` (4 casos)

---

### 7. PatientDeletionService
**Arquivo**: `app/services/patient_deletion_service.py`

**Responsabilidades**:
- Coordenar deleção cascata
- Logar deleção em audit trail
- Soft delete vs hard delete

**Interface Esperada**:
```python
class PatientDeletionService:
    async def delete_patient_data(
        self,
        patient_id: str,
        deletion_type: str = "soft"
    ) -> None:
        """Delete patient and all related data"""

    async def _log_deletion(
        self,
        patient_id: str,
        deletion_type: str,
        requested_by: str,
        reason: str
    ) -> None:
        """Log deletion in audit trail"""
```

**Testes**: `tests/middleware/test_lgpd_middleware.py` (4 casos)

---

### 8. DataPortabilityService
**Arquivo**: `app/services/data_portability_service.py`

**Responsabilidades**:
- Exportar dados em JSON
- Exportar dados em CSV
- Coletar todos os dados do paciente

**Interface Esperada**:
```python
class DataPortabilityService:
    async def export_patient_data(
        self,
        patient_id: str,
        format: str = "json"
    ) -> Union[dict, str]:
        """Export all patient data"""

    async def convert_to_csv(self, data: dict) -> str:
        """Convert data to CSV format"""

    async def _gather_all_data(self, patient_id: str) -> dict:
        """Gather all patient related data"""
```

**Testes**: `tests/middleware/test_lgpd_middleware.py` (3 casos)

---

### 9. ConsentService
**Arquivo**: `app/services/consent_service.py`

**Responsabilidades**:
- Gerenciar consentimentos
- Validar consentimentos ativos
- Verificar expiração

**Interface Esperada**:
```python
class ConsentService:
    async def grant_consent(
        self,
        patient_id: str,
        purpose: str,
        granted_by: str
    ) -> None:
        """Grant consent for data processing"""

    async def revoke_consent(
        self,
        patient_id: str,
        purpose: str
    ) -> None:
        """Revoke existing consent"""

    async def has_consent(
        self,
        patient_id: str,
        purpose: str
    ) -> bool:
        """Check if patient has active consent"""

    async def is_consent_valid(
        self,
        patient_id: str,
        purpose: str
    ) -> bool:
        """Check if consent is valid (not expired)"""
```

**Testes**: `tests/middleware/test_lgpd_middleware.py` (4 casos)

---

### 10. DataRetentionService
**Arquivo**: `app/services/data_retention_service.py`

**Responsabilidades**:
- Identificar dados antigos
- Marcar para deleção
- Executar política de retenção

**Interface Esperada**:
```python
class DataRetentionService:
    async def cleanup_old_data(self) -> None:
        """Cleanup data according to retention policy"""

    async def _find_inactive_patients(
        self,
        days: int = 730
    ) -> List[dict]:
        """Find patients inactive for N days"""
```

**Testes**: `tests/middleware/test_lgpd_middleware.py` (1 caso)

---

### 11. IdempotencyMiddleware
**Arquivo**: `app/middleware/idempotency_middleware.py`

**Responsabilidades**:
- Interceptar requests com idempotency key
- Cachear/retornar resultados
- Gerenciar TTL

**Interface Esperada**:
```python
class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: FastAPI,
        idempotency_service: IdempotencyService
    ):
        super().__init__(app)
        self.idempotency_service = idempotency_service

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Check idempotency key and cache results"""

    def _extract_key(self, request: Request) -> Optional[str]:
        """Extract idempotency key from header"""

    def _should_process_request(self, request: Request) -> bool:
        """Check if request should be processed for idempotency"""
```

**Testes**: `tests/api/v2/test_idempotency.py` (3 casos)

---

## 🗄️ Schemas e Modelos

### Database Schema Extensions

**Tabela: patients**
```sql
ALTER TABLE patients ADD COLUMN cpf_encrypted BYTEA;
ALTER TABLE patients ADD COLUMN cpf_hash VARCHAR(64) UNIQUE;
ALTER TABLE patients ADD COLUMN email_encrypted BYTEA;
ALTER TABLE patients ADD COLUMN email_hash VARCHAR(64);
ALTER TABLE patients ADD COLUMN phone_encrypted BYTEA;
ALTER TABLE patients ADD COLUMN phone_hash VARCHAR(64);
ALTER TABLE patients ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE patients ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE;
```

**Tabela: consents**
```sql
CREATE TABLE consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
    purpose VARCHAR(100) NOT NULL,
    granted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    granted_by VARCHAR(100) NOT NULL,
    revoked_at TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_consents_patient ON consents(patient_id);
CREATE INDEX idx_consents_purpose ON consents(purpose);
CREATE INDEX idx_consents_active ON consents(is_active);
```

**Tabela: audit_log**
```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID,
    user_id UUID,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    ip_address VARCHAR(45),
    user_agent TEXT,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_patient ON audit_log(patient_id);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_created ON audit_log(created_at);
```

---

## 🔧 Configuração

### Environment Variables
```bash
# Encryption
ENCRYPTION_KEY=your-32-character-secret-key!!

# Redis
REDIS_URL=redis://localhost:6379/0

# LGPD
LGPD_ENABLED=true
LGPD_DATA_RETENTION_DAYS=730  # 2 years
LGPD_CONSENT_EXPIRY_DAYS=365  # 1 year

# Idempotency
IDEMPOTENCY_ENABLED=true
IDEMPOTENCY_TTL=3600  # 1 hour
WEBHOOK_DEDUP_TTL=86400  # 24 hours

# Saga
SAGA_TIMEOUT=300  # 5 minutes
SAGA_MAX_RETRIES=3
```

### Dependencies
```bash
# Adicionar ao requirements.txt
cryptography==41.0.7
redis==5.0.1
hashlib  # built-in
```

---

## 📊 Ordem de Implementação Sugerida

1. **EncryptionService** - Base para tudo
2. **IdempotencyService** - Simples, sem dependências
3. **WebhookService** - Usa IdempotencyService
4. **SagaOrchestrator** - Usa Redis
5. **ConsentService** - CRUD simples
6. **PatientRepository extensions** - Usa EncryptionService
7. **DataPortabilityService** - Usa repository
8. **PatientDeletionService** - Usa repository
9. **DataRetentionService** - Usa repository
10. **LGPDMiddleware** - Usa todos acima
11. **IdempotencyMiddleware** - Usa IdempotencyService

---

## ✅ Checklist de Implementação

### Fase 1: Core Services
- [ ] EncryptionService implementado
- [ ] Testes passando (25/25)
- [ ] IdempotencyService implementado
- [ ] Testes passando (18/18)
- [ ] WebhookService implementado
- [ ] Testes passando (4/4)

### Fase 2: Orchestration
- [ ] SagaOrchestrator implementado
- [ ] Testes passando (15/15)
- [ ] Retry logic funcionando
- [ ] State persistence funcionando
- [ ] Audit trail funcionando

### Fase 3: LGPD Compliance
- [ ] ConsentService implementado
- [ ] PatientRepository extensions
- [ ] DataPortabilityService implementado
- [ ] PatientDeletionService implementado
- [ ] DataRetentionService implementado
- [ ] LGPDMiddleware implementado
- [ ] Testes passando (18/18)

### Fase 4: Middleware
- [ ] IdempotencyMiddleware implementado
- [ ] Integração com FastAPI
- [ ] Testes E2E passando

### Fase 5: Database
- [ ] Migrations criadas
- [ ] Índices otimizados
- [ ] Constraints aplicados
- [ ] Seed data criado

### Fase 6: Integration
- [ ] Testes de integração rodando
- [ ] Cobertura >80%
- [ ] Performance aceitável
- [ ] Documentação atualizada

---

## 🎓 Boas Práticas

1. **Seguir os testes**: Implementar exatamente o que os testes esperam
2. **Usar type hints**: Python 3.9+ typing
3. **Documentar**: Docstrings para todas as classes/métodos
4. **Logar adequadamente**: Use structured logging
5. **Validar inputs**: Sempre validar antes de processar
6. **Tratar erros**: Try/except com logging apropriado
7. **Testar incrementalmente**: Rodar testes após cada método

---

## 📚 Recursos

- [Cryptography Documentation](https://cryptography.io/)
- [Redis Python Client](https://redis-py.readthedocs.io/)
- [FastAPI Middleware](https://fastapi.tiangolo.com/tutorial/middleware/)
- [LGPD - Lei 13.709/2018](http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [Saga Pattern](https://microservices.io/patterns/data/saga.html)

---

**Total de Serviços**: 11
**Total de Testes Esperados**: 76
**Cobertura Alvo**: >80%
**Prazo Estimado**: 2-3 sprints
