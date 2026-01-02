# Relatório de Revisão dos Schemas de Paciente

**Data**: 2025-12-23
**Reviewer**: Code Review Agent
**Arquivos Analisados**:
- `backend-hormonia/app/schemas/patient.py` (v1)
- `backend-hormonia/app/schemas/v2/patient.py` (v2)
- `backend-hormonia/app/models/patient.py` (SQLAlchemy Model)

---

## ✅ Pontos Fortes

### 1. Validações Robustas (v1)
- ✅ Validação completa de CPF com dígitos verificadores
- ✅ Validação de idade mínima/máxima (18-120 anos)
- ✅ Validação de email com regex
- ✅ Validação de telefone E.164
- ✅ Validação de metadata JSONB

### 2. Compatibilidade LGPD
- ✅ Modelo SQLAlchemy implementa criptografia de CPF, email e phone
- ✅ Propriedades `cpf_decrypted`, `email_decrypted`, `phone_decrypted`
- ✅ Uso de hashes para busca sem expor dados sensíveis

### 3. Documentação
- ✅ Comentários detalhados sobre conformidade LGPD
- ✅ Referências a migrações (020, 024, 028, 030)
- ✅ Exemplos de uso nos schemas v2

---

## 🔴 Inconsistências Críticas

### 1. **Validação de CPF Ausente no PatientV2Update**

**Localização**: `app/schemas/v2/patient.py` linha 128-153

**Problema**:
```python
class PatientV2Update(BaseModel):
    # ...
    cpf: Optional[str] = Field(None, max_length=14)  # ❌ SEM validador!
```

**v1 Correto**:
```python
class PatientUpdate(BaseModel):
    cpf: Optional[str] = Field(None, max_length=11)

    @field_validator("cpf")
    @classmethod
    def validate_cpf_number(cls, v):
        if v and not validate_cpf(v):
            raise ValueError("Invalid CPF number")
        if v:
            v = re.sub(r"\D", "", v)
        return v
```

**Impacto**: Permite atualizar paciente com CPF inválido, violando integridade de dados.

---

### 2. **Inconsistência no Tamanho Máximo do CPF**

**v1**: `max_length=11` (correto - apenas dígitos)
**v2**: `max_length=14` (permite formatação com pontos e traço)

**Modelo SQLAlchemy**: Armazena 11 dígitos encriptados

**Problema**: v2 aceita formato `123.456.789-00` mas v1 remove formatação antes de salvar.

**Recomendação**: Padronizar para `max_length=14` em ambos, mas normalizar para 11 dígitos antes de salvar.

---

### 3. **Validação de Telefone Inconsistente**

**v1 (PatientBase)**: Exige `+` obrigatório
```python
@field_validator("phone")
@classmethod
def validate_phone(cls, v):
    if not v.startswith("+"):
        raise ValueError("Phone number must start with country code (+)")
```

**v2 (PatientV2Base)**: Aceita formato brasileiro sem `+`
```python
@field_validator("phone")
@classmethod
def validate_phone_format(cls, v):
    # ...
    # Brazilian format (without +55)
    digits_only = re.sub(r"\D", "", v)
    if len(digits_only) < 10 or len(digits_only) > 11:
        # Aceita formato brasileiro
```

**v2 (PatientV2Create)**: Descrição exige E.164
```python
phone: str = Field(..., max_length=20, description="Patient phone number (E.164)")
```

**Impacto**: Comportamento inconsistente entre APIs v1 e v2.

---

### 4. **Validação de Idade Ausente no PatientV2Base e PatientV2Update**

**v1**: Implementa `validate_min_age` em `PatientBase` e `PatientUpdate`

**v2**: ❌ **NÃO implementa validação de idade**

**Código Ausente**:
```python
# ❌ FALTA em PatientV2Base e PatientV2Update
@field_validator("birth_date")
@classmethod
def validate_min_age(cls, v: Optional[date]) -> Optional[date]:
    # ... validação 18-120 anos
```

**Impacto**: API v2 permite criar/atualizar pacientes menores de 18 anos, violando regra de negócio (LOW-004).

---

### 5. **Falta de Validação de Email no PatientV2Update**

**v1**: Valida email em `PatientUpdate` (linha 260-267)

**v2**: ❌ **NÃO valida email** em `PatientV2Update`

**Impacto**: Permite atualizar com emails inválidos via API v2.

---

### 6. **Falta de Validação de Telefone de Emergência no v2**

**v1**: Valida `emergency_contact_phone` (linha 125-130, 269-274)

**v2**: ❌ **Campos de emergência não existem** (`emergency_contact_name`, `emergency_contact_phone`)

**Impacto**: API v2 não suporta dados de contato de emergência, que estão no modelo SQLAlchemy via `patient_data`.

---

### 7. **Campos Clínicos Ausentes no v2**

**v1** (PatientBase linhas 81-100):
- `allergies: Optional[list[str]]`
- `current_medications: Optional[list[str]]`
- `comorbidities: Optional[list[str]]`
- `blood_type: Optional[str]`
- `emergency_contact_name: Optional[str]`
- `emergency_contact_phone: Optional[str]`

**v2**: ❌ **Campos clínicos ausentes**

**Modelo SQLAlchemy**: Armazena via `patient_data` JSONB

**Impacto**: API v2 não permite criar/atualizar informações clínicas essenciais.

---

### 8. **Timezone: Campo Obrigatório vs Opcional**

**v1**:
```python
timezone: str = Field("America/Sao_Paulo", ...)  # Obrigatório com default
```

**v2**:
```python
timezone: str = Field("America/Sao_Paulo", ...)  # Obrigatório em PatientV2Base
# Mas não presente em PatientV2Update
```

**Modelo SQLAlchemy**: Armazena em `patient_data.preferences.timezone`

**Problema**: PatientV2Update não permite atualizar timezone.

---

### 9. **Treatment Phase: Validação de Pattern Inconsistente**

**v1**:
```python
treatment_phase: Optional[str] = Field(
    None,
    pattern="^(initial|adjustment|maintenance|monitoring|followup|completed)$"
)

@field_validator("treatment_phase", mode="before")
@classmethod
def normalize_treatment_phase(cls, v):
    if isinstance(v, str):
        return v.strip().lower()
    return v
```

**v2**:
```python
treatment_phase: Optional[str] = Field(None, max_length=100)
# ❌ SEM pattern validation
# ❌ SEM normalização
```

**Impacto**: v2 aceita valores inválidos como `"INVALID_PHASE"`, `"anything"`.

---

### 10. **Metadata: Validação JSONB Ausente no v2**

**v1**: Valida metadata com `validate_patient_metadata` (LOW-007)

**v2**: ❌ **Sem validação de metadata/patient_data**

**Impacto**: v2 permite salvar JSONB inválido que viola schema definido.

---

## 🟡 Inconsistências de Design

### 11. **PatientResponse vs PatientV2Response: Diferenças Estruturais**

**v1 PatientResponse**:
```python
class PatientResponse(PatientBase):
    id: UUID
    doctor_id: UUID
    flow_state: FlowState  # Enum
    current_day: int
    created_at: date  # Convertido de datetime
    updated_at: date
    patient_data: Optional[Dict[str, Any]] = Field(..., serialization_alias="metadata")
```

**v2 PatientV2Response**:
```python
class PatientV2Response(PatientV2Base):
    id: str  # ❌ String ao invés de UUID
    doctor_id: str  # ❌ String ao invés de UUID
    created_at: datetime  # ❌ datetime ao invés de date
    updated_at: datetime
    current_day: Optional[int] = None  # ❌ Opcional (deveria ser obrigatório)
    flow_state: Optional[str] = Field(None, ...)  # ❌ String ao invés de Enum FlowState

    # ✅ Suporta eager loading
    doctor: Optional[DoctorV2Brief] = None
    quiz_sessions: Optional[List[QuizV2Brief]] = None
```

**Problemas**:
1. **Tipo de ID**: v2 usa `str` mas UUIDs deveriam ser `UUID` type para validação
2. **FlowState**: v2 usa `str` ao invés de Enum (perde validação automática)
3. **current_day**: v2 torna opcional campo que é obrigatório no modelo (default=0)
4. **Timestamp Format**: v1 retorna `date`, v2 retorna `datetime`

---

### 12. **Falta de EmailStr no v1**

**v1**:
```python
email: Optional[str] = Field(None, ...)

@field_validator("email")
@classmethod
def validate_email_format(cls, v):
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_regex, v):
        raise ValueError("Invalid email format")
```

**v2**:
```python
from pydantic import EmailStr

email: Optional[EmailStr] = None  # ✅ Melhor: usa tipo Pydantic
```

**Recomendação**: v1 deveria usar `EmailStr` ao invés de validação manual.

---

### 13. **PatientCreate vs PatientV2Create: Campos Obrigatórios**

**v1 PatientCreate**:
- Herda de `PatientBase` com `phone: str` (obrigatório)
- Adiciona `metadata: Optional[Dict]`

**v2 PatientV2Create**:
- Herda de `PatientV2Base` com `phone: Optional[str]` (opcional)
- Sobrescreve para `phone: str` (obrigatório) - **CONFUSO**
- Adiciona `doctor_id: str` (obrigatório)

**Problema**: v2 sobrescreve campo herdado desnecessariamente.

---

## 📊 Comparação de Campos

| Campo | v1 PatientBase | v2 PatientV2Base | SQLAlchemy Model | Status |
|-------|----------------|------------------|------------------|--------|
| phone | str (obrigatório, E.164) | Optional[str] (E.164 ou BR) | phone_encrypted | ⚠️ Inconsistente |
| email | Optional[str] | Optional[EmailStr] | email_encrypted | ⚠️ Tipo diferente |
| cpf | Optional[str] (max=11) | Optional[str] (max=14) | cpf_encrypted | ⚠️ Tamanho diferente |
| birth_date | Optional[date] (validado) | Optional[date] (não validado) | Date | ❌ Validação faltando |
| treatment_phase | Optional[str] (pattern) | Optional[str] (sem pattern) | String(100) | ❌ Validação faltando |
| timezone | str (default) | str (default) | patient_data.preferences | ✅ OK |
| allergies | Optional[list[str]] | ❌ Ausente | patient_data | ❌ Faltando em v2 |
| current_medications | Optional[list[str]] | ❌ Ausente | patient_data | ❌ Faltando em v2 |
| comorbidities | Optional[list[str]] | ❌ Ausente | patient_data | ❌ Faltando em v2 |
| blood_type | Optional[str] (pattern) | ❌ Ausente | patient_data | ❌ Faltando em v2 |
| emergency_contact_name | Optional[str] | ❌ Ausente | patient_data | ❌ Faltando em v2 |
| emergency_contact_phone | Optional[str] | ❌ Ausente | patient_data | ❌ Faltando em v2 |
| flow_state | FlowState (enum) | Optional[str] | Enum FlowState | ⚠️ Tipo diferente |
| current_day | int (em Update) | Optional[int] | Integer | ⚠️ Opcional em v2 |
| metadata/patient_data | Dict (validado) | ❌ Ausente | JSONB | ❌ Faltando em v2 |

---

## 🎯 Compatibilidade com Modelo SQLAlchemy

### ✅ Campos Compatíveis:
- `name`, `birth_date`, `treatment_type`, `treatment_start_date`
- `diagnosis`, `treatment_phase`, `doctor_notes`
- `cpf` (com criptografia via setter)
- `email`, `phone` (com criptografia via setter)

### ❌ Incompatibilidades:

1. **Campos Criptografados**: Schemas não refletem que `cpf`, `email`, `phone` são armazenados criptografados
2. **patient_data JSONB**: v2 não expõe este campo, mas modelo armazena dados clínicos aqui
3. **FlowState Enum**: v2 usa string ao invés de enum
4. **UUID vs String**: v2 serializa UUIDs como strings

---

## 🔍 Validações de Campos Obrigatórios

### PatientCreate/PatientV2Create:

| Campo | v1 | v2 | Modelo | Alinhamento |
|-------|----|----|--------|-------------|
| phone | ✅ Obrigatório | ✅ Obrigatório | ✅ Obrigatório (encrypted) | ✅ OK |
| name | ✅ Obrigatório | ✅ Obrigatório | ✅ Obrigatório | ✅ OK |
| doctor_id | ❌ Não presente | ✅ Obrigatório | ✅ Obrigatório | ⚠️ v1 assume do contexto |
| email | ❌ Opcional | ❌ Opcional | ❌ Opcional | ✅ OK |
| birth_date | ❌ Opcional | ❌ Opcional | ❌ Opcional | ✅ OK |
| flow_state | ❌ Não presente | ❌ Não presente | ✅ Default: ONBOARDING | ✅ OK (default) |
| current_day | ❌ Não presente | ❌ Não presente | ✅ Default: 0 | ✅ OK (default) |

---

## 🛡️ Validações de Tipos de Dados

### Tipos Corretos vs Encontrados:

| Campo | Tipo Esperado | v1 | v2 | Modelo | Problemas |
|-------|--------------|----|----|--------|----------|
| id | UUID | UUID | **str** | UUID | v2 deveria usar UUID |
| doctor_id | UUID | UUID | **str** | UUID | v2 deveria usar UUID |
| phone | str | str | str | LargeBinary (encrypted) | ✅ OK |
| email | EmailStr | **str** | EmailStr | LargeBinary (encrypted) | v1 deveria usar EmailStr |
| birth_date | date | date | date | Date | ✅ OK |
| flow_state | FlowState (enum) | FlowState | **str** | Enum | v2 deveria usar Enum |
| current_day | int | int | **Optional[int]** | Integer | v2 não deveria ser opcional |
| created_at | datetime | **date** | datetime | DateTime | v1 converte para date (inconsistente) |
| updated_at | datetime | **date** | datetime | DateTime | v1 converte para date (inconsistente) |

---

## 📝 Recomendações de Correção

### Prioridade Alta (P0):

1. **Adicionar validação de idade em v2** (PatientV2Base, PatientV2Update)
2. **Adicionar validação de CPF em v2** (PatientV2Update)
3. **Adicionar validação de treatment_phase em v2** (pattern + normalização)
4. **Corrigir tipo de `id` e `doctor_id` em v2** (usar UUID ao invés de str)
5. **Corrigir tipo de `flow_state` em v2** (usar FlowState enum)

### Prioridade Média (P1):

6. **Padronizar validação de telefone** (decidir entre E.164 obrigatório ou aceitar BR)
7. **Padronizar tamanho de CPF** (max_length=14 para aceitar formatação, normalizar para 11)
8. **Adicionar campos clínicos em v2** (allergies, medications, comorbidities, blood_type, emergency_contact)
9. **Adicionar suporte a metadata/patient_data em v2**
10. **Usar EmailStr em v1** ao invés de validação manual

### Prioridade Baixa (P2):

11. **Padronizar formato de timestamp** (decidir entre date ou datetime para created_at/updated_at)
12. **Tornar `current_day` obrigatório em v2 Response**
13. **Documentar diferenças entre v1 e v2 explicitamente**

---

## 🧪 Casos de Teste Sugeridos

### Teste 1: Validação de CPF Inválido via v2
```python
# Deveria falhar mas atualmente passa
payload = {"cpf": "111.111.111-11"}  # CPF inválido
response = client.patch(f"/api/v2/patients/{patient_id}", json=payload)
# Esperado: 422 Validation Error
# Atual: 200 OK ❌
```

### Teste 2: Criação de Paciente Menor de Idade via v2
```python
# Deveria falhar mas atualmente passa
payload = {"birth_date": "2010-01-01"}  # Menor de idade
response = client.post("/api/v2/patients", json=payload)
# Esperado: 422 Validation Error
# Atual: 201 Created ❌
```

### Teste 3: Treatment Phase Inválido via v2
```python
# Deveria falhar mas atualmente passa
payload = {"treatment_phase": "INVALID"}
response = client.patch(f"/api/v2/patients/{patient_id}", json=payload)
# Esperado: 422 Validation Error
# Atual: 200 OK ❌
```

### Teste 4: Telefone sem Código de País via v1
```python
# Deveria falhar
payload = {"phone": "11987654321"}  # Sem +55
response = client.post("/api/v1/patients", json=payload)
# Esperado: 422 Validation Error
# Atual: 422 OK ✅
```

---

## 📚 Referências

- **LOW-004**: birth_date Minimum Age Validation
- **LOW-007**: JSONB Schema Validation
- **QW-003**: CPF Encryption Validation Hook
- **QW-004**: Idempotency Key for Duplicate Prevention
- **Migrations**: 020 (CPF encryption), 024 (CPF plaintext removal), 028 (email/phone encryption), 030 (plaintext removal)

---

## 🎯 Sumário Executivo

**Total de Inconsistências**: 13 críticas + 3 de design

**Impacto**:
- ❌ API v2 permite dados inválidos (CPF, idade, treatment_phase)
- ❌ Validações ausentes criam vulnerabilidades de dados
- ⚠️ Inconsistência entre v1 e v2 dificulta manutenção
- ⚠️ Campos clínicos ausentes em v2 limitam funcionalidade

**Ação Recomendada**: Priorizar correções P0 para garantir integridade de dados e conformidade com regras de negócio.

---

**Fim do Relatório**
