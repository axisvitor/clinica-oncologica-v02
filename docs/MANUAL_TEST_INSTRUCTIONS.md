# Instruções para Teste Manual da Saga

**Data:** 2025-10-24  
**Status:** ✅ Correções Aplicadas - Aguardando Teste Manual

---

## 🎯 O Que Foi Corrigido

### Bug Identificado e Corrigido

**Arquivo:** `backend-hormonia/app/services/patient.py` (linha 86)

```python
# ❌ ANTES (COM BUG)
use_saga = settings.get("ENABLE_SAGA_PATTERN", True)

# ✅ DEPOIS (CORRIGIDO)
use_saga = getattr(settings, "ENABLE_SAGA_PATTERN", True)
```

### Configuração Adicionada

**Arquivo:** `backend-hormonia/app/config/settings/features.py`

```python
ENABLE_SAGA_PATTERN: bool = Field(
    default=True,
    description="Enable Saga Pattern for patient onboarding (recommended for production)",
)
```

---

## ⚠️  Importante: Como Testar Corretamente

**A saga SÓ é executada quando o paciente é criado via `PatientService`.**

❌ **NÃO funciona:** Criar paciente diretamente no banco SQL  
✅ **Funciona:** Criar paciente via API ou PatientService

---

## 🧪 Opção 1: Teste via API (Recomendado)

### Passo 1: Garantir que Backend está Rodando

```bash
# Verificar se está rodando
curl http://localhost:8000/health

# Se não estiver, iniciar:
cd backend-hormonia
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Passo 2: Fazer Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "admin123"
  }'
```

**Copie o `access_token` da resposta**

### Passo 3: Criar Paciente via API

```bash
curl -X POST http://localhost:8000/api/v1/patients \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer SEU_TOKEN_AQUI" \
  -d '{
    "name": "Teste Saga Manual",
    "phone": "+5594912345678",
    "email": "teste.saga.manual@example.com",
    "treatment_type": "Terapia Hormonal",
    "treatment_start_date": "2025-10-24"
  }'
```

**Copie o `id` do paciente criado**

### Passo 4: Verificar Saga no Banco

```bash
cd backend-hormonia
python -c "
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.config import settings

engine = create_engine(settings.DATABASE_URL.replace('+psycopg', ''))
session = Session(engine)

# Substituir PATIENT_ID pelo ID copiado
patient_id = 'PATIENT_ID_AQUI'

saga = session.execute(
    text('SELECT * FROM patient_onboarding_saga WHERE patient_id = :id'),
    {'id': patient_id}
).first()

if saga:
    print('✅ SAGA ENCONTRADA!')
    print(f'Status: {saga.status}')
else:
    print('❌ SAGA NÃO ENCONTRADA')
"
```

---

## 🧪 Opção 2: Teste via Script Python

### Script de Teste

Criar arquivo `test_saga_manual.py`:

```python
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.config import settings
from app.schemas.patient import PatientCreate
from datetime import datetime

async def test():
    # Importar services
    from app.services.patient import PatientService, PatientIntegrityService
    from app.repositories.patient import PatientRepository
    from app.services.flow_engine import FlowEngine
    from app.coordination.saga_orchestrator import SagaOrchestrator
    from app.core.redis_client import get_redis_client
    
    # Criar engine
    engine = create_engine(settings.DATABASE_URL.replace('+psycopg', ''))
    
    with Session(engine) as session:
        # Buscar médico
        doctor = session.execute(text("SELECT id FROM users LIMIT 1")).first()
        
        # Criar services
        repository = PatientRepository(session)
        integrity_service = PatientIntegrityService(session)
        flow_engine = FlowEngine(session)
        saga = SagaOrchestrator(db=session, redis_client=get_redis_client())
        
        patient_service = PatientService(
            db=session,
            patient_repository=repository,
            integrity_service=integrity_service,
            flow_engine=flow_engine,
            saga_orchestrator=saga
        )
        
        # Criar paciente
        patient_data = PatientCreate(
            name="Teste Saga Script",
            phone="+5594987654321",
            email="teste.saga.script@example.com",
            treatment_type="Terapia Hormonal",
            treatment_start_date=datetime.now().date()
        )
        
        patient = await patient_service.create_patient(
            patient_data=patient_data,
            doctor_id=doctor.id,
            current_user=None
        )
        
        print(f"✅ Paciente criado: {patient.id}")
        
        # Verificar saga
        saga_result = session.execute(
            text("SELECT * FROM patient_onboarding_saga WHERE patient_id = :id"),
            {"id": str(patient.id)}
        ).first()
        
        if saga_result:
            print("✅ SAGA ENCONTRADA!")
            print(f"Status: {saga_result.status}")
        else:
            print("❌ SAGA NÃO ENCONTRADA")

if __name__ == "__main__":
    asyncio.run(test())
```

### Executar:

```bash
cd backend-hormonia
python test_saga_manual.py
```

---

## 📊 Resultado Esperado

### Se o Fix Funcionou ✅

```
✅ Paciente criado: <UUID>
✅ SAGA ENCONTRADA!
Status: completed (ou in_progress)
```

### Se Ainda Não Funciona ❌

```
✅ Paciente criado: <UUID>
❌ SAGA NÃO ENCONTRADA
```

**Neste caso, verificar:**
1. Logs do backend para erros
2. Se o backend foi reiniciado após o fix
3. Se há erro na execução da saga

---

## 🔍 Verificar Logs do Backend

Enquanto cria o paciente, observe os logs do backend. Deve aparecer:

```
INFO: Creating patient using Saga Pattern for doctor <UUID>
INFO: Patient created successfully via Saga: <UUID> - <Nome>
```

Se aparecer:
```
WARNING: Saga failed, falling back to direct patient creation
```

Significa que a saga está falhando e caindo no fallback.

---

## ✅ Checklist de Validação

- [ ] Backend rodando
- [ ] Correções aplicadas (getattr + ENABLE_SAGA_PATTERN)
- [ ] Backend reiniciado após correções
- [ ] Paciente criado via API (não via SQL direto)
- [ ] Saga encontrada no banco
- [ ] Status da saga é "completed" ou "in_progress"

---

## 💡 Dicas

1. **Sempre criar via API/Service**, nunca via SQL direto
2. **Verificar logs do backend** para ver se a saga está sendo chamada
3. **Aguardar alguns segundos** após criar o paciente antes de verificar
4. **Celery Beat não é necessário** para a saga executar (só para processar flows)

---

**Criado por:** Kiro AI  
**Data:** 2025-10-24  
**Status:** Aguardando Teste Manual ✅
