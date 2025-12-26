# Guia de Database - Sistema Hormonia

**Versao:** 2.0
**Data:** 2025-12-26

---

## Metricas

| Metrica | Valor |
|---------|-------|
| Tabelas | 77 |
| Indices | 479+ |
| Migrations | 37 |
| Constraints | 200+ |

---

## Stack

- **PostgreSQL** 15+ (AWS RDS)
- **SQLAlchemy** 2.0+ (ORM)
- **Alembic** 1.14+ (Migrations)
- **Redis** 7+ (Cache/Sessions)

---

## Principais Modelos

### Patient (LGPD Compliance)

```python
class Patient(BaseModel):
    id: UUID
    name: str

    # Dados criptografados (AES-256-GCM)
    cpf_encrypted: str
    cpf_hash: str          # Para busca
    phone_encrypted: str
    phone_hash: str
    email_encrypted: str

    # Soft delete
    deleted_at: Optional[datetime]

    # Relacionamentos
    doctor_id: UUID
    flow_state: PatientFlowState
```

### PatientFlowState

```python
class PatientFlowState(BaseModel):
    id: UUID
    patient_id: UUID
    status: FlowStatus  # onboarding, active, paused, completed
    current_day: int
    last_processed_at: datetime
```

### QuizSession

```python
class QuizSession(BaseModel):
    id: UUID
    patient_id: UUID
    token: str          # UUID para acesso publico
    status: SessionStatus
    responses: List[QuizResponse]
    completed_at: Optional[datetime]
```

---

## Migrations

### Executar Migrations

```bash
cd backend-hormonia
alembic upgrade head
```

### Criar Nova Migration

```bash
alembic revision --autogenerate -m "descricao"
```

### Verificar Status

```bash
alembic current
alembic history
```

---

## Indices de Performance

| Tabela | Indice | Tipo |
|--------|--------|------|
| patient | phone_hash | btree |
| patient | cpf_hash | btree |
| patient | doctor_id | btree |
| flow_state | patient_id | btree |
| flow_state | status | btree |
| quiz_session | token | unique |

---

## Connection Pooling

```python
# settings/database.py
POOL_SIZE = 10
MAX_OVERFLOW = 20
POOL_TIMEOUT = 30
POOL_RECYCLE = 1800  # 30 min
```

---

## Backup

```bash
# Backup completo
pg_dump -h host -U user -d hormonia > backup.sql

# Restore
psql -h host -U user -d hormonia < backup.sql
```

---

**Ultima Atualizacao:** 2025-12-26
