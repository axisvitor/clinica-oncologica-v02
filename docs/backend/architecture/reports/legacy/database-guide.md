# Guia Consolidado de Banco de Dados

**Backend Hormonia - Clinica Oncologica**
**Versao:** 2.1 | **Atualizado:** 29/12/2025

---

## Sumario

1. [Visao Geral](#1-visao-geral)
2. [Modelos Principais](#2-modelos-principais)
3. [Migrations (Alembic)](#3-migrations-alembic)
4. [Indices e Performance](#4-indices-e-performance)
5. [Connection Pooling](#5-connection-pooling)
6. [Problemas N+1 e Solucoes](#6-problemas-n1-e-solucoes)
7. [Redis Integration](#7-redis-integration)

---

## 1. Visao Geral

### Stack Tecnologico

| Componente | Tecnologia | Versao |
|------------|------------|--------|
| **Database** | PostgreSQL | 15+ |
| **ORM** | SQLAlchemy | 2.0+ (Async) |
| **Migrations** | Alembic | Latest |
| **Driver** | psycopg | 3.x (Async) |
| **Cache** | Redis | 7.x |
| **Cloud** | AWS RDS | sa-east-1 |

### Metricas Atuais

```
Total de Tabelas:    77 (Core + Auditoria)
Total de Indices:    479+
Migration Head:      037_fix_missing_fk_cascades
Database Size:       17 MB (producao)
Health Score:        98/100
```

### Conexao (Producao)

```python
# Configuracao de conexao
DATABASE_URL = "postgresql+psycopg://user:***@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require"

# Parametros
Host:     database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com
Port:     5432
Database: postgres
SSL:      Required (sslmode=require)
Driver:   psycopg (async-capable)
Region:   sa-east-1 (Sao Paulo, Brazil)
```

---

## 2. Modelos Principais

### 2.1 Patient (Paciente)

Entidade central do sistema com criptografia LGPD.

```python
# app/models/patient.py

class Patient(Base):
    __tablename__ = "patients"

    # Identificacao
    id = Column(UUID, primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)

    # LGPD - Campos Criptografados (AES-256-GCM)
    cpf_encrypted = Column(Text, nullable=True)
    cpf_hash = Column(String(64), nullable=True, index=True)
    email_encrypted = Column(LargeBinary, nullable=True)
    email_hash = Column(String(64), nullable=True, index=True)
    phone_encrypted = Column(LargeBinary, nullable=True)
    phone_hash = Column(String(64), nullable=True, index=True)

    # Estado do Fluxo
    flow_state = Column(Enum(FlowState), default=FlowState.ONBOARDING)
    current_day = Column(Integer, default=1)

    # Relacionamentos
    doctor_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    doctor = relationship("User", back_populates="patients")
    messages = relationship("Message", back_populates="patient", cascade="all, delete-orphan")
    quiz_sessions = relationship("QuizSession", back_populates="patient")

    # Metadados e Soft Delete
    metadata = Column(JSONB, default={})
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Propriedades para acesso transparente (decriptacao automatica)
    @property
    def cpf(self) -> Optional[str]:
        """Retorna CPF decriptado"""
        return self.cpf_decrypted

    def set_cpf(self, cpf_value: Optional[str]) -> None:
        """Criptografa CPF e gera hash para busca"""
        if cpf_value:
            self.cpf_encrypted = encrypt_aes_gcm(cpf_value)
            self.cpf_hash = sha256_hash(cpf_value)
```

**Indices da Tabela patients:**
- `idx_patients_doctor_id` - Filtro por medico
- `idx_patients_flow_state` - Filtro por estado
- `idx_patients_treatment_type` - Filtro por tratamento
- `idx_patients_created_at` - Ordenacao cronologica
- `ix_patients_cpf_hash` - Busca por CPF (LGPD)
- `ix_patients_email_hash` - Busca por email (LGPD)
- `ix_patients_phone_hash` - Busca por telefone (LGPD)

### 2.2 QuizSession (Sessao de Questionario)

```python
# app/models/quiz_session.py

class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id = Column(UUID, primary_key=True, default=uuid4)
    patient_id = Column(UUID, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)

    # Autenticacao por Token
    token = Column(String(64), unique=True, nullable=False, index=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=False)

    # Estado
    status = Column(Enum(QuizSessionStatus), default=QuizSessionStatus.PENDING)
    flow_day = Column(Integer, nullable=False)

    # Respostas (JSONB)
    responses = Column(JSONB, default={})
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    patient = relationship("Patient", back_populates="quiz_sessions")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**Indices:**
- `idx_quiz_sessions_patient_id` - Busca por paciente
- `idx_quiz_sessions_token` - Validacao de token
- `idx_quiz_sessions_created_at` - Ordenacao

### 2.3 FlowState (Estados do Fluxo)

```python
# app/models/enums.py

class FlowState(enum.Enum):
    """Estados do fluxo do paciente"""
    ONBOARDING = "onboarding"   # Em processo de cadastro
    ACTIVE = "active"           # Recebendo mensagens/quiz
    PAUSED = "paused"           # Fluxo pausado
    COMPLETED = "completed"     # Fluxo finalizado
    CANCELLED = "cancelled"     # Cancelado pelo usuario/medico
```

### 2.4 Message (Mensagem WhatsApp)

```python
# app/models/message.py

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID, primary_key=True, default=uuid4)
    patient_id = Column(UUID, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)

    # Conteudo
    content = Column(Text, nullable=False)
    message_type = Column(Enum(MessageType), default=MessageType.TEXT)
    direction = Column(Enum(MessageDirection), nullable=False)

    # Status e Tracking
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING)
    whatsapp_message_id = Column(String(255), nullable=True, index=True)

    # Agendamento
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Idempotencia (previne duplicacao)
    idempotency_key = Column(String(64), unique=True, nullable=True, index=True)

    # Prioridade
    priority = Column(Integer, default=0)

    # Relacionamentos
    patient = relationship("Patient", back_populates="messages")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**Indices Compostos:**
- `idx_messages_patient_status` - (patient_id, status)
- `idx_messages_scheduled` - (scheduled_for, status)
- `idx_messages_patient_created` - (patient_id, created_at DESC)

### 2.5 Tabelas de Fluxo (Flow Templates)

```python
# flow_kinds - Tipos de fluxo
class FlowKind(Base):
    __tablename__ = "flow_kinds"

    id = Column(UUID, primary_key=True)
    kind_key = Column(String(100), unique=True)  # Ex: "initial_15_days"
    display_name = Column(String(255))
    is_active = Column(Boolean, default=True)

# flow_template_versions - Versoes de templates
class FlowTemplateVersion(Base):
    __tablename__ = "flow_template_versions"

    id = Column(UUID, primary_key=True)
    flow_kind_id = Column(UUID, ForeignKey("flow_kinds.id"))
    version_number = Column(Integer)
    is_active = Column(Boolean, default=False)  # Apenas uma versao ativa por kind
    steps = Column(JSONB)  # Estrutura de mensagens e quiz por dia

    created_by = Column(UUID, ForeignKey("users.id"))
    published_at = Column(DateTime(timezone=True))
```

### 2.6 User (Usuario/Medico)

```python
# app/models/user.py

class User(Base):
    __tablename__ = "users"

    id = Column(UUID, primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    firebase_uid = Column(String(128), unique=True, nullable=True, index=True)

    # Perfil
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.DOCTOR)
    permissions = Column(JSONB, default=[])  # ["patients:read", "patients:write"]

    # Seguranca (Migration 032)
    failed_login_attempts = Column(Integer, default=0)
    is_locked = Column(Boolean, default=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    force_change_password = Column(Boolean, default=False)
    last_password_change = Column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    patients = relationship("Patient", back_populates="doctor")

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### 2.7 Saga Pattern (Onboarding)

```python
# app/models/patient_onboarding_saga.py

class PatientOnboardingSaga(Base):
    __tablename__ = "patient_onboarding_saga"

    id = Column(UUID, primary_key=True, default=uuid4)
    patient_id = Column(UUID, ForeignKey("patients.id", ondelete="CASCADE"))

    status = Column(Enum(SagaStatus), default=SagaStatus.STARTED)
    current_step = Column(String(100))
    steps_completed = Column(JSONB, default=[])
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SagaStatus(enum.Enum):
    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
```

---

## 3. Migrations (Alembic)

### 3.1 Comandos Essenciais

```bash
# Verificar status atual
cd backend-hormonia
alembic current

# Aplicar todas as migrations pendentes
alembic upgrade head

# Aplicar uma migration especifica
alembic upgrade +1

# Rollback da ultima migration
alembic downgrade -1

# Rollback para revision especifica
alembic downgrade abc123

# Criar nova migration
alembic revision -m "add_new_feature"

# Criar migration auto-gerada (detecta mudancas nos models)
alembic revision --autogenerate -m "add_new_column"

# Ver historico de migrations
alembic history

# Ver SQL que seria executado (dry-run)
alembic upgrade head --sql
```

### 3.2 Historico de Migrations Recentes

| Migration | Descricao | Data |
|-----------|-----------|------|
| `037_fix_missing_fk_cascades` | Correção de FK cascades (cleanup) | Dec 2025 |
| `036_add_saga_step_data_column` | Coluna step_data em onboarding_saga | Dec 2025 |
| `035_add_saga_status_enum_values` | Novos status para Saga (Compensating) | Dec 2025 |
| `034_add_performance_indexes` | Indices CONCURRENTLY para patients, quiz, messages | Dec 2025 |
| `033_fix_user_sync_log_schema` | Schema Firebase sync | Dec 2025 |
| `032_add_user_security_columns` | Colunas de seguranca (account lockout) | Dec 2025 |
| `031_add_performance_indexes` | Otimizacao massiva (479 indices) | Dec 2025 |
| `030_drop_plaintext_email_phone` | Remocao de PII plaintext (LGPD) | Dec 2025 |
| `029_migrate_email_phone_to_encrypted` | Migracao de dados para criptografia | Dec 2025 |
| `028_encrypt_email_phone_lgpd` | Adicao de colunas criptografadas | Dec 2025 |
| `025_add_patient_idempotency_key` | Chave de idempotencia para pacientes | Nov 2025 |
| `022_cursor_pagination_indexes` | Indices para paginacao cursor | Nov 2025 |

### 3.3 Boas Praticas de Migration

```python
# alembic/versions/xxx_example_migration.py

from alembic import op
import sqlalchemy as sa

def upgrade():
    # 1. Use CONCURRENTLY para criar indices em producao (nao trava tabela)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_patients_flow_state
        ON patients(flow_state)
    """)

    # 2. Adicione colunas com DEFAULT para evitar lock em tabelas grandes
    op.add_column('patients',
        sa.Column('new_field', sa.String(100), nullable=True, server_default='default_value')
    )

    # 3. Apos popular dados, remova o default se necessario
    # op.alter_column('patients', 'new_field', server_default=None)

def downgrade():
    # Sempre implemente downgrade para rollback seguro
    op.drop_column('patients', 'new_field')
    op.drop_index('idx_patients_flow_state', table_name='patients')
```

### 3.4 Migration para Indice com CREATE CONCURRENTLY

```python
# Para indices em tabelas grandes em producao
def upgrade():
    # Desabilita transacao automatica para CONCURRENTLY
    op.execute("COMMIT")

    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_patient_status_date
        ON messages(patient_id, status, created_at DESC)
    """)

def downgrade():
    op.execute("COMMIT")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_messages_patient_status_date")
```

---

## 4. Indices e Performance

### 4.1 Estrategia de Indexacao

#### Indices Padrao
- **Primary Keys (PK):** Todos os PKs sao indexados automaticamente
- **Foreign Keys (FK):** Todas as FKs possuem indices
- **Status/Enums:** Campos de baixa cardinalidade com indices para filtros

#### Indices Compostos (Mais Importantes)

```sql
-- Pacientes por medico e estado (consulta mais frequente)
CREATE INDEX idx_patients_doctor_flow_state_created
ON patients(doctor_id, flow_state, created_at DESC)
WHERE deleted_at IS NULL;

-- Mensagens por paciente e status
CREATE INDEX idx_messages_patient_status_date
ON messages(patient_id, status, created_at DESC);

-- Quiz sessions por paciente
CREATE INDEX idx_quiz_sessions_patient_status_date
ON quiz_sessions(patient_id, status, created_at DESC);

-- Agendamentos
CREATE INDEX idx_appointments_patient_date
ON appointments(patient_id, scheduled_start DESC);
```

#### Indices Parciais (Otimizacao)

```sql
-- Apenas registros ativos (evita indexar soft-deleted)
CREATE INDEX idx_patients_active
ON patients(id) WHERE deleted_at IS NULL;

-- Apenas mensagens pendentes
CREATE INDEX idx_messages_pending
ON messages(scheduled_for, priority)
WHERE status = 'pending';

-- Apenas com email (evita indexar nulls)
CREATE INDEX idx_patients_email_exists
ON patients(email_hash) WHERE email_hash IS NOT NULL;
```

#### Indices GIN para JSONB

```sql
-- Busca em metadados do paciente
CREATE INDEX idx_patients_metadata_gin
ON patients USING GIN (metadata);

-- Busca em respostas de quiz
CREATE INDEX idx_quiz_responses_gin
ON quiz_sessions USING GIN (responses);

-- Exemplo de query otimizada
SELECT * FROM patients
WHERE metadata @> '{"treatment_type": "chemotherapy"}';
```

### 4.2 Verificacao de Performance de Indices

```sql
-- Verificar uso dos indices
SELECT
    indexname,
    idx_scan as times_used,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE tablename = 'patients'
ORDER BY idx_scan DESC;

-- Identificar indices nao utilizados
SELECT
    indexname,
    idx_scan as scans,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE 'pg_%'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Analisar plano de execucao
EXPLAIN ANALYZE
SELECT * FROM patients
WHERE doctor_id = 'uuid' AND deleted_at IS NULL
ORDER BY created_at DESC LIMIT 20;
-- Deve mostrar: Index Scan using idx_patients_doctor_flow_state_created
```

### 4.3 Paginacao Cursor (Keyset Pagination)

```python
# Implementacao otimizada O(1) ao inves de OFFSET O(n)
from sqlalchemy import and_, or_

def list_patients_cursor(
    db: Session,
    doctor_id: UUID,
    cursor_created_at: datetime = None,
    cursor_id: UUID = None,
    limit: int = 20
):
    query = db.query(Patient).filter(
        Patient.doctor_id == doctor_id,
        Patient.deleted_at.is_(None)
    )

    # Aplicar cursor (keyset pagination)
    if cursor_created_at and cursor_id:
        query = query.filter(
            or_(
                Patient.created_at < cursor_created_at,
                and_(
                    Patient.created_at == cursor_created_at,
                    Patient.id < cursor_id
                )
            )
        )

    # Ordenacao e limite
    query = query.order_by(
        Patient.created_at.desc(),
        Patient.id.desc()
    ).limit(limit + 1)  # +1 para detectar has_more

    results = query.all()
    has_more = len(results) > limit

    return {
        "data": results[:limit],
        "has_more": has_more,
        "next_cursor": encode_cursor(results[limit-1]) if results else None
    }
```

**Performance Comparativa:**

| Metodo | Pagina 1 | Pagina 100 | Pagina 1000 |
|--------|----------|------------|-------------|
| OFFSET | 5ms | 45ms | 450ms |
| Cursor | 5ms | 5ms | 5ms |

---

## 5. Connection Pooling

### 5.1 Arquitetura Dual-Engine

O sistema usa dois pools de conexao separados:

```python
# app/core/database.py

# 1. Service Role Engine - Operacoes de sistema
service_role_engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
    connect_args={
        'connect_timeout': 30,
        'application_name': 'hormonia_service_role',
        'options': '-c statement_timeout=30000'
    }
)

# 2. RLS Context Engine - Requisicoes de usuario (Row Level Security)
rls_engine = create_engine(
    settings.DATABASE_URL,
    pool_size=17,  # 1/3 do service pool
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,  # Mais curto para tokens
)
```

### 5.2 Configuracao por Ambiente

| Ambiente | Workers | Pool Size | Max Overflow | Total Max |
|----------|---------|-----------|--------------|-----------|
| **Production** | 4 | 10 | 10 | 80 conexoes |
| **Staging** | 2 | 10 | 15 | 50 conexoes |
| **Development** | 1 | 10 | 15 | 25 conexoes |
| **Test** | 1 | 5 | 5 | 10 conexoes |

### 5.3 Variaveis de Ambiente

```bash
# .env - Configuracao de Pool

# Database Pool (valores otimizados)
DATABASE_POOL_SIZE=10
DATABASE_POOL_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT_SECONDS=30
DATABASE_POOL_RECYCLE_SECONDS=1800
DATABASE_POOL_PRE_PING=true
DATABASE_POOL_RESET_ON_RETURN=commit

# Statement Timeout
DATABASE_STATEMENT_TIMEOUT_MS=30000
DATABASE_SLOW_QUERY_THRESHOLD_SECONDS=1.0
```

### 5.4 Monitoramento de Pool

```python
# Verificar status do pool
from app.core.database import get_pool_status

status = get_pool_status(use_service_role=True)
print(f"""
Pool Size: {status['pool_size']}
Checked Out: {status['checked_out']}
Checked In: {status['checked_in']}
Overflow: {status['overflow']}
Utilization: {status['checked_out'] / status['pool_size'] * 100:.1f}%
""")

# Alertas
# - Warning: > 85% utilizacao
# - Critical: > 92% utilizacao
```

### 5.5 Resolucao de Problemas de Pool

```python
# Problema: "QueuePool limit exceeded"
# Causa: Pool size insuficiente para carga
# Solucao: Aumentar DATABASE_POOL_SIZE ou DATABASE_POOL_MAX_OVERFLOW

# Problema: "SSL connection has been closed"
# Causa: Conexao reciclada muito tarde
# Solucao: Reduzir DATABASE_POOL_RECYCLE_SECONDS (padrao: 1800s)

# Problema: Conexoes orfas
# Causa: Commits nao realizados
# Solucao: Verificar que todas as sessions fazem commit/rollback
```

---

## 6. Problemas N+1 e Solucoes

### 6.1 O Problema N+1

```python
# PROBLEMA: N+1 Query Pattern
patients = db.query(Patient).filter(Patient.doctor_id == doctor_id).all()

for patient in patients:
    # Cada acesso a patient.messages gera uma nova query!
    print(len(patient.messages))  # +1 query por paciente

# 100 pacientes = 101 queries (1 principal + 100 lazy loads)
```

### 6.2 Solucoes Implementadas

#### Eager Loading com joinedload

```python
from sqlalchemy.orm import joinedload, selectinload

# SOLUCAO 1: joinedload (1:1 relationships)
query = db.query(Patient).options(
    joinedload(Patient.doctor)  # Usa LEFT OUTER JOIN
).filter(Patient.doctor_id == doctor_id)

# SOLUCAO 2: selectinload (1:N relationships)
query = db.query(Patient).options(
    selectinload(Patient.messages),  # Usa SELECT ... WHERE IN (...)
    selectinload(Patient.quiz_sessions)
).filter(Patient.doctor_id == doctor_id)

# COMBINADO: Para relacionamentos aninhados
query = db.query(Patient).options(
    joinedload(Patient.doctor),
    selectinload(Patient.messages).joinedload(Message.sender)
).filter(Patient.doctor_id == doctor_id)

# Resultado: 2-4 queries total ao inves de 100+
```

#### Agregacao no Banco (Evitar Python Loops)

```python
# ANTES (Ruim): Agregacao em Python
scores = [score[0] for score in query.all()]
positive = sum(1 for s in scores if s > 0.1)
neutral = sum(1 for s in scores if -0.1 <= s <= 0.1)
negative = sum(1 for s in scores if s < -0.1)

# DEPOIS (Bom): Agregacao no PostgreSQL
from sqlalchemy import func, case

result = db.query(
    func.sum(case((FlowAnalytics.sentiment_score > 0.1, 1), else_=0)).label('positive'),
    func.sum(case((FlowAnalytics.sentiment_score.between(-0.1, 0.1), 1), else_=0)).label('neutral'),
    func.sum(case((FlowAnalytics.sentiment_score < -0.1, 1), else_=0)).label('negative')
).filter(FlowAnalytics.sentiment_score.isnot(None)).one()

return {"positive": result.positive, "neutral": result.neutral, "negative": result.negative}
```

#### Evitar COUNT Sequenciais

```python
# ANTES (Ruim): 4 queries separadas
total = query.count()
sent = query.filter(Message.sent_at.isnot(None)).count()
delivered = query.filter(Message.delivered_at.isnot(None)).count()
read = query.filter(Message.read_at.isnot(None)).count()

# DEPOIS (Bom): 1 query com CASE
result = db.query(
    func.count(Message.id).label('total'),
    func.count(case((Message.sent_at.isnot(None), 1))).label('sent'),
    func.count(case((Message.delivered_at.isnot(None), 1))).label('delivered'),
    func.count(case((Message.read_at.isnot(None), 1))).label('read')
).filter(Message.scheduled_for.between(start, end)).one()
```

### 6.3 Metricas de Performance Alcancadas

| Metrica | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| Queries por pagina | 120+ | 4 | 97% reducao |
| Tempo de resposta medio | 800ms | 120ms | 85% reducao |
| CPU do banco (pico) | 70%+ | <15% | 78% reducao |
| Requisicoes/seg | ~12 | ~85 | 7x aumento |

### 6.4 Decorator para Cache de Query

```python
# app/utils/cache.py

from functools import wraps
from app.core.redis_manager import get_redis_manager

def cached_query(cache_key: str, ttl: int = 60):
    """Decorator para cache de queries caras"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            redis = get_redis_manager()

            # Tentar cache
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)

            # Executar query
            result = await func(*args, **kwargs)

            # Salvar no cache
            await redis.set(cache_key, json.dumps(result), ex=ttl)

            return result
        return wrapper
    return decorator

# Uso
@cached_query("active_quiz_templates", ttl=600)
async def get_active_templates(self, skip: int = 0, limit: int = 100):
    return self.db.query(QuizTemplate).filter(QuizTemplate.is_active).all()
```

---

## 7. Redis Integration

### 7.1 Configuracao do Redis

```bash
# .env - Configuracao Redis

REDIS_URL=redis://default:password@redis-host:6379/0
REDIS_POOL_MAX_CONNECTIONS=20
REDIS_SOCKET_TIMEOUT_SECONDS=5.0
REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS=2.0
REDIS_MAX_RETRY_ATTEMPTS=3
REDIS_ENABLE_HEALTH_CHECK=true

# SSL/TLS Optimization
REDIS_SSL_SESSION_REUSE=true
REDIS_SSL_CONNECTION_POOL_WARMUP=true
REDIS_SSL_WARMUP_CONNECTIONS=5
```

### 7.2 Redis Manager

```python
# app/core/redis_manager/manager.py

class RedisManager:
    def __init__(self):
        self.pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_POOL_MAX_CONNECTIONS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
            retry_on_timeout=True,
            health_check_interval=30
        )
        self._client = redis.Redis(connection_pool=self.pool)

    async def get(self, key: str) -> Optional[str]:
        """Buscar valor do cache"""
        return await self._async_client.get(key)

    async def set(self, key: str, value: str, ex: int = None) -> bool:
        """Salvar valor no cache com TTL opcional"""
        return await self._async_client.set(key, value, ex=ex)

    async def delete(self, key: str) -> int:
        """Remover chave do cache"""
        return await self._async_client.delete(key)

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidar todas as chaves que correspondem ao padrao"""
        keys = await self._async_client.keys(pattern)
        if keys:
            return await self._async_client.delete(*keys)
        return 0

# Singleton
_redis_manager: Optional[RedisManager] = None

def get_redis_manager() -> RedisManager:
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisManager()
    return _redis_manager
```

### 7.3 Estrategias de Cache

```python
# TTLs por tipo de dado
CACHE_TTLS = {
    "query": 60,          # Resultados de queries frequentes
    "session": 900,       # Sessoes de usuario (15 min)
    "template": 3600,     # Templates de fluxo (1 hora)
    "static": 86400,      # Dados estaticos (1 dia)
    "count": 60,          # Contagens totais
}

# Padroes de chave
CACHE_KEYS = {
    "patient_list": "patients:list:doctor:{doctor_id}:page:{page}",
    "patient_count": "patients:count:doctor:{doctor_id}",
    "quiz_templates": "quiz:templates:active",
    "flow_template": "flow:template:{kind_key}:version:{version}",
    "user_session": "session:user:{user_id}",
}
```

### 7.4 Invalidacao de Cache

```python
# Invalidar cache apos mudancas

async def create_patient(patient_data: dict, doctor_id: UUID):
    # Criar paciente no banco
    patient = Patient(**patient_data)
    db.add(patient)
    db.commit()

    # Invalidar caches relacionados
    redis = get_redis_manager()
    await redis.invalidate_pattern(f"patients:*:doctor:{doctor_id}:*")
    await redis.delete(f"patients:count:doctor:{doctor_id}")

    return patient

async def update_flow_template(kind_key: str, new_version: dict):
    # Atualizar template
    # ...

    # Invalidar cache do template
    redis = get_redis_manager()
    await redis.invalidate_pattern(f"flow:template:{kind_key}:*")
```

### 7.5 Pool Warmup (SSL/TLS)

```python
# Aquecer conexoes no startup para amortizar custo SSL

async def warmup_connection_pool():
    """Pre-criar conexoes para amortizar custo de handshake SSL"""
    redis = get_redis_manager()
    warmup_count = min(5, settings.REDIS_POOL_MAX_CONNECTIONS)

    tasks = [redis._async_client.ping() for _ in range(warmup_count)]
    await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(f"Redis pool warmed up with {warmup_count} connections")

# Chamar no startup da aplicacao
@app.on_event("startup")
async def startup():
    await warmup_connection_pool()
```

### 7.6 Metricas Redis

```python
# Verificar metricas do Redis

async def get_redis_metrics():
    redis = get_redis_manager()
    info = await redis._async_client.info()

    hits = info.get('keyspace_hits', 0)
    misses = info.get('keyspace_misses', 0)
    total = hits + misses

    return {
        "connected_clients": info.get('connected_clients'),
        "used_memory_human": info.get('used_memory_human'),
        "cache_hit_ratio": (hits / total * 100) if total > 0 else 0,
        "total_connections_received": info.get('total_connections_received'),
        "keyspace_hits": hits,
        "keyspace_misses": misses,
    }

# Alertas
# - Warning: cache_hit_ratio < 80%
# - Critical: cache_hit_ratio < 50%
```

---

## Referencias Rapidas

### Comandos Uteis

```bash
# Database
alembic current                    # Status das migrations
alembic upgrade head               # Aplicar migrations
alembic downgrade -1               # Rollback

# Redis
redis-cli INFO                     # Status do Redis
redis-cli KEYS "patients:*"        # Listar chaves
redis-cli FLUSHDB                  # Limpar database (cuidado!)

# Debugging
export SQLALCHEMY_ECHO=true        # Log de queries SQL
tail -f logs/slow_queries.log      # Queries lentas
```

### Arquivos Importantes

| Arquivo | Descricao |
|---------|-----------|
| `app/core/database.py` | Configuracao de engines e pools |
| `app/core/database_config.py` | Parametros dinamicos de pool |
| `app/core/redis_manager/` | Gerenciador Redis |
| `app/models/` | Definicao de modelos SQLAlchemy |
| `app/repositories/` | Camada de acesso a dados |
| `alembic/versions/` | Scripts de migration |
| `alembic/env.py` | Configuracao Alembic |

### Health Check Endpoints

```bash
# Status geral
curl http://localhost:8000/api/v2/health

# Status detalhado com metricas de pool
curl http://localhost:8000/api/v2/health/detailed | jq '.components.database'

# Verificar utilizacao de pool
curl http://localhost:8000/api/v2/health/detailed | jq '.components.database.metrics[] | select(.name=="pool_utilization")'
```

---

**Documento consolidado de:** docs/database/, DATABASE_HEALTH_REPORT.md, DATABASE_PERFORMANCE_N_PLUS_ONE_ANALYSIS.md, N1_OPTIMIZATION_SUMMARY.md, N_PLUS_ONE_FIX_IMPLEMENTATION_GUIDE.md, POOL_OPTIMIZATION_SUMMARY.md, SCHEMA_FIXES_CODE_SNIPPETS.md, SCHEMA_ISSUES_QUICK_REFERENCE.md

**Ultima atualizacao:** 26/12/2025
