# Conformidade LGPD - Banco de Dados

> **Última Atualização:** 2025-11-26
> **Migrations Relacionadas:** 020, 024

## Visão Geral

Este documento descreve as medidas de proteção de dados pessoais sensíveis implementadas no banco de dados PostgreSQL do sistema Hormonia, em conformidade com a **Lei Geral de Proteção de Dados (LGPD)** - Lei nº 13.709/2018.

## Criptografia de Dados Sensíveis

### CPF (Cadastro de Pessoa Física)

#### Armazenamento
- **Coluna criptografada**: `cpf_encrypted` (tipo: TEXT)
- **Coluna de busca**: `cpf_hash` (tipo: VARCHAR(64))
- **Coluna original**: `cpf` (VARCHAR(14)) - **REMOVIDA** na Migration 024

### Email e Telefone (Migration 028)

#### Armazenamento
- **Email criptografado**: `email_encrypted` (tipo: BYTEA)
- **Email hash**: `email_hash` (tipo: VARCHAR(64))
- **Telefone criptografado**: `phone_encrypted` (tipo: BYTEA)
- **Telefone hash**: `phone_hash` (tipo: VARCHAR(64))

#### Algoritmos de Segurança
- **Criptografia**: AES-256-GCM (Advanced Encryption Standard)
- **Hash de Busca**: SHA-256 (Secure Hash Algorithm)
- **Derivação de Chave**: PBKDF2 (Password-Based Key Derivation Function 2)

#### Fluxo de Processamento

```
┌─────────────────────────────────────────────────────────────┐
│  1. INSERÇÃO DE PACIENTE                                    │
├─────────────────────────────────────────────────────────────┤
│  Cliente → API: CPF em plaintext (ex: "12345678900")        │
│  Backend:                                                   │
│    - Valida formato do CPF                                  │
│    - Criptografa com AES-256-GCM → cpf_encrypted            │
│    - Calcula SHA-256 → cpf_hash                             │
│  Database:                                                  │
│    - Armazena cpf_encrypted (dados criptografados)          │
│    - Armazena cpf_hash (para buscas)                        │
│    - NÃO armazena plaintext (Migration 024)                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  2. BUSCA POR CPF                                           │
├─────────────────────────────────────────────────────────────┤
│  Cliente → API: CPF em plaintext (ex: "12345678900")        │
│  Backend:                                                   │
│    - Calcula SHA-256 do CPF fornecido                       │
│    - Busca no banco usando cpf_hash                         │
│  Database:                                                  │
│    - Query: WHERE cpf_hash = 'abc123...'                    │
│    - Índice: ix_patients_cpf_hash (otimizado)               │
│  Backend:                                                   │
│    - Descriptografa cpf_encrypted para validação            │
│    - Retorna dados do paciente                              │
└─────────────────────────────────────────────────────────────┘
```

#### Índices para Performance
```sql
-- Busca por CPF (usando hash)
CREATE INDEX ix_patients_cpf_hash ON patients(cpf_hash);

-- Busca composta (CPF + Médico)
CREATE INDEX ix_patients_cpf_hash_doctor
  ON patients(cpf_hash, doctor_id)
  WHERE cpf_hash IS NOT NULL;
```

#### Constraint de Unicidade
```sql
-- Garante que um CPF não seja cadastrado duas vezes para o mesmo médico
ALTER TABLE patients
  ADD CONSTRAINT uq_patient_cpf_hash_doctor
  UNIQUE (cpf_hash, doctor_id);
```

## Serviço de Criptografia

### Localização
- **Arquivo**: `app/services/lgpd_encryption_service.py`
- **Classe**: `LGPDEncryptionService`
- **Legacy (CPF apenas)**: `app/services/phi_encryption_service.py`

### Métodos Principais

#### `encrypt_cpf(plaintext_cpf: str) -> Tuple[str, str]`
Criptografa um CPF e gera seu hash.

**Parâmetros:**
- `plaintext_cpf`: CPF em texto plano (11 dígitos)

**Retorno:**
- `(cpf_encrypted, cpf_hash)`: Tupla com dados criptografados e hash

**Exemplo:**
```python
from app.services.cpf_encryption_service import get_cpf_encryption_service

service = get_cpf_encryption_service()
encrypted, hash_value = service.encrypt_cpf("12345678900")

# encrypted: "gAAAAABh..." (base64 do AES-GCM)
# hash_value: "a3c5e7..." (SHA-256 hex)
```

#### `decrypt_cpf(encrypted_cpf: str) -> str`
Descriptografa um CPF.

**Parâmetros:**
- `encrypted_cpf`: CPF criptografado (base64)

**Retorno:**
- CPF em plaintext

**Exemplo:**
```python
plaintext = service.decrypt_cpf("gAAAAABh...")
# plaintext: "12345678900"
```

#### `generate_cpf_hash(plaintext_cpf: str) -> str`
Gera hash SHA-256 para busca.

**Parâmetros:**
- `plaintext_cpf`: CPF em texto plano

**Retorno:**
- Hash SHA-256 em hexadecimal

**Exemplo:**
```python
hash_value = service.generate_cpf_hash("12345678900")
# hash_value: "a3c5e7..."
```

### Configuração

#### Variável de Ambiente
```bash
# .env
ENCRYPTION_KEY=your-32-byte-encryption-key-here
```

⚠️ **IMPORTANTE:**
- A chave DEVE ter exatamente 32 bytes (256 bits)
- NUNCA commitar a chave no repositório Git
- Em produção, usar AWS Secrets Manager ou similar
- Backup da chave em local seguro (perda = dados irrecuperáveis)

#### Geração de Chave
```python
from cryptography.fernet import Fernet

# Gera uma chave segura
key = Fernet.generate_key()
print(key.decode())  # Use este valor em ENCRYPTION_KEY
```

## Audit Trail (Trilha de Auditoria)

### Tabela: `audit_logs`

Todas as operações que envolvem dados de pacientes são registradas automaticamente.

#### Informações Capturadas
```sql
SELECT
  event_type,           -- Tipo do evento (CREATE, READ, UPDATE, DELETE)
  user_id,              -- Quem executou a ação
  resource_type,        -- Tipo do recurso (patient, user, etc)
  resource_id,          -- ID do recurso afetado
  changes_before,       -- Estado anterior (JSONB)
  changes_after,        -- Estado posterior (JSONB)
  ip_address,           -- IP de origem
  user_agent,           -- Navegador/cliente
  created_at            -- Timestamp da ação
FROM audit_logs
WHERE resource_type = 'patient'
  AND created_at >= NOW() - INTERVAL '30 days'
ORDER BY created_at DESC;
```

#### Middleware HIPAA/LGPD

O sistema usa um middleware que captura automaticamente:
- Todas requisições HTTP que modificam dados
- Dados antes e depois da alteração
- Metadados de contexto (user, IP, timestamp)
- Sucesso ou falha da operação

**Localização:** `app/middleware/hipaa_middleware.py`

#### Retenção de Logs
- **Período padrão:** 6 anos (conforme LGPD Art. 16)
- **Arquivamento:** Tabela `audit_logs_archive` (particionada por ano)
- **Política:** Logs não podem ser deletados, apenas arquivados

## Row Level Security (RLS)

### Isolamento Multi-Tenant

O sistema implementa RLS para garantir que usuários só acessem dados de sua própria clínica.

#### Policies PostgreSQL
```sql
-- Exemplo de policy (implementação futura)
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;

CREATE POLICY patient_isolation_policy ON patients
  USING (doctor_id = current_setting('app.current_user_id')::uuid);
```

#### Configuração por Sessão
```python
# Em cada requisição, define o contexto do usuário
async with db.begin():
    await db.execute(
        text("SET app.current_user_id = :user_id"),
        {"user_id": str(current_user.id)}
    )
    # Queries seguintes respeitam a policy automaticamente
```

## Criptografia de Email e Telefone (Migration 028)

### Visão Geral
A partir da migration 028, email e telefone também são criptografados seguindo o mesmo padrão do CPF, garantindo proteção completa de dados pessoais sensíveis.

### Colunas Adicionadas

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `email_encrypted` | BYTEA | Email criptografado com AES-256-GCM |
| `email_hash` | VARCHAR(64) | HMAC-SHA256 para busca sem descriptografia |
| `phone_encrypted` | BYTEA | Telefone criptografado com AES-256-GCM |
| `phone_hash` | VARCHAR(64) | HMAC-SHA256 para busca sem descriptografia |

### Fluxo de Criptografia

#### Inserção de Email/Phone
```
┌─────────────────────────────────────────────────────────────┐
│  1. INSERÇÃO DE DADOS PESSOAIS                              │
├─────────────────────────────────────────────────────────────┤
│  Cliente → API: Dados em plaintext                          │
│    - Email: "paciente@email.com"                            │
│    - Phone: "(11) 98765-4321"                               │
│                                                              │
│  Backend (EncryptionService):                               │
│    - Normaliza email: lowercase                             │
│    - Normaliza phone: remove não-dígitos → "11987654321"    │
│    - Criptografa com AES-256-GCM                            │
│    - Gera HMAC-SHA256 hash com salt                         │
│                                                              │
│  Database:                                                  │
│    - email_encrypted: bytes criptografados                  │
│    - email_hash: hash para busca                            │
│    - phone_encrypted: bytes criptografados                  │
│    - phone_hash: hash para busca                            │
└─────────────────────────────────────────────────────────────┘
```

#### Busca por Email/Phone
```
┌─────────────────────────────────────────────────────────────┐
│  2. BUSCA POR EMAIL OU TELEFONE                             │
├─────────────────────────────────────────────────────────────┤
│  Cliente → API: Termo de busca (ex: "paciente@email.com")  │
│                                                              │
│  Backend:                                                   │
│    - Normaliza termo de busca                               │
│    - Gera hash do termo (mesma função de inserção)          │
│                                                              │
│  Database:                                                  │
│    - Query: WHERE email_hash = 'abc123...'                  │
│    - Índices otimizados:                                    │
│      * ix_patients_email_hash                               │
│      * ix_patients_phone_hash                               │
│                                                              │
│  Backend:                                                   │
│    - Descriptografa dados para exibição                     │
│    - Retorna resultados ao cliente                          │
└─────────────────────────────────────────────────────────────┘
```

### Serviço de Criptografia

#### Métodos Principais

**`encrypt_email(plaintext_email: str) -> Tuple[bytes, str]`**
```python
from app.services.encryption_service import EncryptionService

service = EncryptionService()
encrypted_bytes, hash_value = service.encrypt_email("paciente@email.com")

# encrypted_bytes: bytes criptografados
# hash_value: "a3c5e7..." (HMAC-SHA256 hex)
```

**`encrypt_phone(plaintext_phone: str) -> Tuple[bytes, str]`**
```python
encrypted_bytes, hash_value = service.encrypt_phone("(11) 98765-4321")

# Normalização automática: apenas dígitos
# encrypted_bytes: bytes criptografados
# hash_value: hash para busca
```

**`decrypt_email(encrypted_email: bytes) -> str`**
```python
plaintext = service.decrypt_email(encrypted_bytes)
# plaintext: "paciente@email.com"
```

**`decrypt_phone(encrypted_phone: bytes) -> str`**
```python
plaintext = service.decrypt_phone(encrypted_bytes)
# plaintext: "11987654321" (normalizado)
```

### Índices para Performance

```sql
-- Busca por email
CREATE INDEX ix_patients_email_hash ON patients(email_hash);

-- Busca por telefone
CREATE INDEX ix_patients_phone_hash ON patients(phone_hash);

-- Busca composta (email + médico)
CREATE INDEX ix_patients_email_hash_doctor
  ON patients(email_hash, doctor_id)
  WHERE email_hash IS NOT NULL;

-- Busca composta (phone + médico)
CREATE INDEX ix_patients_phone_hash_doctor
  ON patients(phone_hash, doctor_id)
  WHERE phone_hash IS NOT NULL;
```

### Procedimento de Hard Delete (Art. 16 LGPD)

Implementado em `PatientRepository.hard_delete()` para garantir eliminação completa de dados sensíveis:

```python
from app.repositories.patient_repository import PatientRepository

# Instanciar repositório
repo = PatientRepository(db_session)

# Hard delete com auditoria
await repo.hard_delete(
    patient_id="550e8400-e29b-41d4-a716-446655440000",
    audit_reason="Solicitação do titular - Art. 16 LGPD"
)
```

**Dados Deletados:**
- `cpf_encrypted` e `cpf_hash`
- `email_encrypted` e `email_hash`
- `phone_encrypted` e `phone_hash`
- Todos registros relacionados (mensagens, quiz, alertas, etc.)

**ATENÇÃO:**
- Esta operação é **IRREVERSÍVEL**
- Criar backup antes se necessário
- Registrado em `audit_logs` para compliance
- Usar apenas sob solicitação formal do titular

### Variáveis de Ambiente

```bash
# .env
ENCRYPTION_KEY=your-32-byte-encryption-key-here
ENCRYPTION_SALT=your-16-byte-salt-here
```

⚠️ **IMPORTANTE:**
- `ENCRYPTION_KEY`: 32 bytes (256 bits) para AES-256
- `ENCRYPTION_SALT`: 16 bytes para HMAC
- NUNCA commitar chaves no Git
- Usar AWS Secrets Manager em produção
- Backup seguro das chaves (perda = dados irrecuperáveis)

Para rotação de chaves, consulte: [KEY_ROTATION_GUIDE.md](../guides/KEY_ROTATION_GUIDE.md)

## Migrations Relacionadas

### Migration 020: `encrypt_cpf_lgpd`
**Data:** 2025-11-24
**Arquivo:** `alembic/versions/020_encrypt_cpf_lgpd.py`

**Mudanças:**
1. ✅ Adiciona colunas `cpf_encrypted` e `cpf_hash` à tabela `patients`
2. ✅ Cria índice `ix_patients_cpf_hash` para buscas otimizadas
3. ✅ Migra todos CPFs existentes do plaintext para formato criptografado
4. ✅ Atualiza constraint de unicidade para usar `cpf_hash` ao invés de `cpf`
5. ✅ Mantém coluna `cpf` original para compatibilidade durante rollout

**Comando:**
```bash
alembic upgrade 020_encrypt_cpf_lgpd
```

### Migration 021: `add_patient_summaries`
**Data:** 2025-11-25
**Arquivo:** `alembic/versions/021_add_patient_summaries.py`

**Mudanças:**
1. ✅ Cria tabela `patient_summaries` para resumos médicos gerados por IA
2. ✅ Armazena dados sensíveis em formato JSONB criptografado
3. ✅ Índices para buscas por paciente e período

**Nota LGPD:** Dados de IA também são considerados sensíveis e protegidos.

### Migration 022: `add_cursor_pagination_indexes`
**Data:** 2025-11-25
**Arquivo:** `alembic/versions/022_add_cursor_pagination_indexes.py`

**Mudanças:**
1. ✅ Adiciona 8 índices compostos para paginação eficiente
2. ✅ Melhora performance: 450ms → 5ms (99% mais rápido)
3. ✅ Reduz exposição de dados em queries lentas

**Benefício LGPD:** Minimiza tempo de acesso a dados sensíveis.

### Migration 023: `add_user_permissions`
**Data:** 2025-11-26
**Arquivo:** `alembic/versions/023_add_user_permissions.py`

**Mudanças:**
1. ✅ Adiciona coluna `permissions` (JSONB) à tabela `users`
2. ✅ Cria índice GIN para buscas rápidas de permissões
3. ✅ Habilita RBAC granular

**Benefício LGPD:** Controle de acesso fino para dados sensíveis.

### Migration 024: `drop_plaintext_cpf` ⚠️ IRREVERSÍVEL
**Data:** 2025-11-26
**Arquivo:** `alembic/versions/024_drop_plaintext_cpf.py`

**Mudanças:**
1. ✅ Remove coluna `cpf` plaintext da tabela `patients`
2. ✅ Completa conformidade LGPD eliminando armazenamento de PII em texto plano
3. ⚠️ **IRREVERSÍVEL**: Dados plaintext são permanentemente deletados

**Pre-requisitos:**
- Migration 020 aplicada com sucesso
- Todos CPFs migrados para formato criptografado
- Código atualizado para usar `cpf_hash` nas queries

**Comando:**
```bash
alembic upgrade 024_drop_plaintext_cpf
```

### Migration 028: `encrypt_email_phone`
**Data:** 2025-11-26
**Arquivo:** `alembic/versions/028_encrypt_email_phone.py`

**Mudanças:**
1. ✅ Adiciona colunas `email_encrypted`, `email_hash` à tabela `patients`
2. ✅ Adiciona colunas `phone_encrypted`, `phone_hash` à tabela `patients`
3. ✅ Cria índices para buscas otimizadas por email e phone
4. ✅ Migra dados existentes para formato criptografado
5. ✅ Atualiza constraints de unicidade

**Nota:** Parte da conformidade completa LGPD para todos dados pessoais sensíveis.

**Comando:**
```bash
alembic upgrade 028_encrypt_email_phone
```

## Checklist de Conformidade LGPD

### ✅ Implementado

- [x] **Art. 6º - Criptografia de Dados Sensíveis**
  - CPF criptografado com AES-256-GCM
  - Hash SHA-256 para buscas
  - Chave armazenada em variável de ambiente

- [x] **Art. 46 - Segurança e Sigilo**
  - Criptografia em repouso (database)
  - HTTPS para criptografia em trânsito
  - Acesso restrito às chaves

- [x] **Art. 37 - Minimização de Dados**
  - Plaintext CPF removido (Migration 024)
  - Apenas dados criptografados no banco

- [x] **Art. 48 - Comunicação de Incidentes**
  - Audit logs completos
  - Rastreamento de acessos a dados sensíveis

- [x] **Art. 16 - Eliminação de Dados**
  - Soft deletes com `deleted_at`
  - Processo de eliminação definitiva documentado

### 🔄 Em Desenvolvimento

- [ ] **Row Level Security (RLS)** - Policies PostgreSQL
- [ ] **Anonimização Automática** - Após período de retenção
- [ ] **Criptografia de Campo Completa** - Outros dados sensíveis
- [ ] **Dashboard de Compliance** - Métricas e relatórios

## Tratamento de Incidentes

### Procedimento em Caso de Vazamento

1. **Contenção Imediata**
   - Revogar credenciais comprometidas
   - Bloquear acessos suspeitos
   - Isolar sistemas afetados

2. **Análise de Impacto**
   ```sql
   -- Identificar dados afetados
   SELECT COUNT(DISTINCT patient_id) as affected_patients
   FROM audit_logs
   WHERE created_at BETWEEN :incident_start AND :incident_end
     AND event_type IN ('READ', 'EXPORT');
   ```

3. **Notificação ANPD**
   - Prazo: 2 dias úteis (Art. 48 LGPD)
   - Conteúdo: Descrição, impacto, medidas tomadas

4. **Notificação de Titulares**
   - Se alto risco aos direitos dos pacientes
   - Comunicação clara e acessível

5. **Remediação**
   - Rotação de chaves de criptografia
   - Patch de vulnerabilidades
   - Reforço de controles de acesso

### Rotação de Chave de Criptografia

```python
# Script de rotação de chave (usar com cautela!)
from app.services.cpf_encryption_service import get_cpf_encryption_service

old_service = get_cpf_encryption_service(old_key)
new_service = get_cpf_encryption_service(new_key)

# Para cada paciente:
for patient in patients:
    plaintext_cpf = old_service.decrypt_cpf(patient.cpf_encrypted)
    new_encrypted, new_hash = new_service.encrypt_cpf(plaintext_cpf)

    # Atualizar no banco
    patient.cpf_encrypted = new_encrypted
    patient.cpf_hash = new_hash
    db.commit()
```

## Direitos dos Titulares (LGPD Art. 18)

### Confirmação de Tratamento
```sql
-- Verificar se há dados de um titular
SELECT EXISTS(
  SELECT 1 FROM patients
  WHERE cpf_hash = :cpf_hash
) as has_data;
```

### Acesso aos Dados
```python
# Exportar dados pessoais de um paciente
patient_data = {
    "cpf": service.decrypt_cpf(patient.cpf_encrypted),
    "name": patient.name,
    "email": patient.email,
    # ... outros dados
}
```

### Correção de Dados
- Via API `PATCH /patients/{id}`
- Registrado em `audit_logs`

### Eliminação de Dados
```python
# Soft delete (padrão)
patient.deleted_at = datetime.utcnow()

# Hard delete (apenas sob solicitação formal)
# CUIDADO: Irreversível!
db.delete(patient)
db.commit()
```

## Documentação Técnica

### Arquivos Relacionados
- `app/services/lgpd_encryption_service.py` - Serviço principal de criptografia LGPD
- `app/services/phi_encryption_service.py` - Serviço legacy (CPF apenas)
- `app/middleware/hipaa_audit_middleware.py` - Middleware de auditoria HIPAA/LGPD
- `app/middleware/lgpd_middleware.py` - Middleware específico LGPD
- `alembic/versions/020_encrypt_cpf_lgpd.py` - Migration de criptografia CPF
- `alembic/versions/024_drop_plaintext_cpf.py` - Migration de remoção CPF plaintext
- `alembic/versions/025_add_patient_idempotency_key.py` - Migration idempotência
- `alembic/versions/028_encrypt_email_phone_lgpd.py` - Migration criptografia email/phone

### Diagramas

#### Fluxo de Criptografia
```
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌──────────┐
│ Cliente │────>│   API   │────>│ Crypto   │────>│ Database │
└─────────┘     └─────────┘     │ Service  │     └──────────┘
                                 └──────────┘
    CPF           Valida         Criptografa     cpf_encrypted
  Plaintext       Formato        AES-256-GCM      + cpf_hash
```

## Contato e Suporte

**Encarregado de Dados (DPO):**
- Email: dpo@hormonia.com.br
- Telefone: (11) XXXX-XXXX

**Equipe Técnica:**
- Email: tech@hormonia.com.br
- Issues: https://github.com/hormonia/backend/issues

---

**Última Revisão:** 2025-11-26
**Próxima Revisão:** 2025-12-26
**Versão:** 1.0
