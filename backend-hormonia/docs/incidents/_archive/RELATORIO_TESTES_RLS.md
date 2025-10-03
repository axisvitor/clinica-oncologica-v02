# 🧪 Relatório de Execução de Testes RLS

**Data:** 2025-10-02
**Status:** ⚠️ **PARCIALMENTE CORRIGIDO - Schema Mismatch**
**Arquivo:** `backend-hormonia/tests/security/test_rls_policies.py`

---

## 📊 Resultado da Execução

### Resumo - Execução Final
- **Total de testes:** 5
- **Passaram:** 1 ✅
- **Falharam:** 2 ❌
- **Erros:** 2 ❌
- **Tempo:** 8.67s

### Resumo - Execução Inicial (Antes das Correções)
- **Total de testes:** 5
- **Falharam:** 3 ❌
- **Erros:** 2 ❌
- **Passaram:** 0
- **Tempo:** 81.36s

### Detalhamento - Execução Final

| Teste | Status | Erro | Tempo |
|-------|--------|------|-------|
| `test_doctor_can_only_see_own_patients` | ❌ ERROR | type "auth_provider" does not exist | 2.49s setup |
| `test_user_can_only_update_own_profile` | ❌ FAILED | type "auth_provider" does not exist | 0.16s |
| `test_medical_reports_isolated_by_doctor` | ❌ ERROR | type "auth_provider" does not exist | 1.58s setup |
| `test_quiz_templates_accessible_to_authenticated_users` | ✅ **PASSED** | - | 0.84s |
| `test_unauthenticated_access_denied` | ❌ FAILED | AssertionError: Unauthenticated request should see no users | 0.53s |

### Detalhamento - Execução Inicial

| Teste | Status | Erro | Tempo |
|-------|--------|------|-------|
| `test_doctor_can_only_see_own_patients` | ❌ ERROR | TypeError: object NoneType can't be used in 'await' expression | 8.56s setup |
| `test_user_can_only_update_own_profile` | ❌ FAILED | TypeError: object NoneType can't be used in 'await' expression | 39.76s |
| `test_medical_reports_isolated_by_doctor` | ❌ ERROR | TypeError: object NoneType can't be used in 'await' expression | 31.98s setup |
| `test_quiz_templates_accessible_to_authenticated_users` | ❌ FAILED | ModuleNotFoundError: No module named 'app.models.quiz_template' | - |
| `test_unauthenticated_access_denied` | ❌ FAILED | TypeError: object CursorResult can't be used in 'await' expression | 0.10s |

---

## 🐛 Problemas Identificados

### ✅ Problemas Corrigidos

#### 1. **Incompatibilidade Async/Sync** (RESOLVIDO)

**Problema:** Os fixtures `doctor1_context` e `doctor2_context` tentam usar `await db_session.commit()`, mas a sessão do `conftest.py` é **síncrona**.

**Erro:**
```python
# tests/security/test_rls_policies.py:34
await db_session.commit()
# TypeError: object NoneType can't be used in 'await' expression
```

**Causa Raiz:**
```python
# tests/conftest.py:84-104
@pytest.fixture
def db_session(test_engine):
    """Synchronous database session"""
    SessionLocal = sessionmaker(...)
    session = SessionLocal()  # ← Sessão SÍNCRONA
    yield session
```

**Solução Aplicada:**
- ✅ Trocado `db_session` por `async_db_session` em todos os testes
- ✅ Fixtures corrigidas para usar sessão async
- ✅ Instalado `asyncpg` package

#### 2. **Import Incorreto do Modelo Quiz** (RESOLVIDO)

**Problema:** Teste importa `app.models.quiz_template` mas o modelo está em `app.models.quiz`

**Erro:**
```python
# tests/security/test_rls_policies.py:325
from app.models.quiz_template import QuizTemplate
# ModuleNotFoundError: No module named 'app.models.quiz_template'
```

**Solução Aplicada:**
```python
# Corrigido para:
from app.models.quiz import QuizTemplate
# E ajustado campos do modelo (name, version, questions)
```

**Resultado:** ✅ Teste `test_quiz_templates_accessible_to_authenticated_users` agora PASSA

### ❌ Problemas Pendentes

#### 3. **Schema Mismatch - auth_provider ENUM** (CRITICAL)

**Problema:** O modelo `User` em Python define um campo `auth_provider` ENUM que NÃO EXISTE no banco de dados Supabase.

**Erro:**
```python
sqlalchemy.exc.ProgrammingError:
asyncpg.exceptions.UndefinedObjectError: type "auth_provider" does not exist
```

**Causa Raiz:**
```python
# app/models/user.py:41-45
auth_provider = Column(
    Enum(AuthProvider, name='auth_provider', native_enum=True),
    nullable=False,
    default=AuthProvider.LOCAL
)
```

**Banco de dados:**
```sql
-- ENUM não existe em Supabase:
SELECT * FROM pg_type WHERE typname = 'auth_provider';
-- Retorna 0 rows
```

**Impacto:** Testes que criam usuários falham na inserção

**Solução Necessária:**
1. **Opção A (Recomendado):** Criar migration para adicionar ENUM ao banco
   ```sql
   -- Migration: add_auth_provider_enum.sql
   CREATE TYPE auth_provider AS ENUM ('local', 'firebase', 'google', 'apple');
   ALTER TABLE users ADD COLUMN auth_provider auth_provider DEFAULT 'local';
   ```

2. **Opção B:** Mudar modelo para usar String ao invés de ENUM
   ```python
   auth_provider = Column(String(50), nullable=False, default='local')
   ```

**Testes Afetados:**
- ❌ `test_doctor_can_only_see_own_patients`
- ❌ `test_user_can_only_update_own_profile`
- ❌ `test_medical_reports_isolated_by_doctor`

#### 4. **RLS Não Bloqueando Acesso Anônimo** (HIGH)

**Problema:** Teste `test_unauthenticated_access_denied` falhou porque usuários foram retornados sem autenticação.

**Erro:**
```python
AssertionError: Unauthenticated request should see no users
# Expected: 0 users
# Actual: 1+ users retornados
```

**Causa Provável:**
- RLS policy `users_select_own` pode não estar ativa
- Ou policy permite SELECT para role `anon`

**Verificação Necessária:**
```sql
-- Verificar se RLS está habilitado
SELECT tablename, rowsecurity
FROM pg_tables
WHERE tablename = 'users';

-- Ver policies ativas
SELECT * FROM pg_policies WHERE tablename = 'users';
```

**Solução:** Garantir que policy users_select exija autenticação:
```sql
-- Policy esperada:
CREATE POLICY "users_select_own" ON users
FOR SELECT TO authenticated  -- ← Apenas authenticated, não anon
USING (firebase_uid = current_setting('request.jwt.claims', true)::json->>'sub');
```

---

## 🔧 Correções Necessárias

### Correção 1: Usar Fixture Async Correta

**Arquivo:** `tests/security/test_rls_policies.py`

**Mudança em TODOS os testes:**
```python
# Antes:
async def test_doctor_can_only_see_own_patients(
    db_session: AsyncSession,  # ← Parâmetro errado
    doctor1_context: User,
    doctor2_context: User
):

# Depois:
async def test_doctor_can_only_see_own_patients(
    async_db_session: AsyncSession,  # ← Usar fixture async
    doctor1_context: User,
    doctor2_context: User
):
```

**Aplicar em:**
- ✅ `test_doctor_can_only_see_own_patients`
- ✅ `test_user_can_only_update_own_profile`
- ✅ `test_medical_reports_isolated_by_doctor`
- ✅ `test_quiz_templates_accessible_to_authenticated_users`
- ✅ `test_unauthenticated_access_denied`

### Correção 2: Atualizar Fixtures de Doctor

**Arquivo:** `tests/security/test_rls_policies.py`

**Atualizar assinaturas das fixtures:**
```python
# Antes:
@pytest.fixture
async def doctor1_context(db_session: AsyncSession):
    doctor1 = User(...)
    db_session.add(doctor1)
    await db_session.commit()  # ← Falha aqui

# Depois:
@pytest.fixture
async def doctor1_context(async_db_session: AsyncSession):
    doctor1 = User(...)
    async_db_session.add(doctor1)
    await async_db_session.commit()  # ← Agora funciona
```

**Aplicar em:**
- ✅ `doctor1_context` fixture
- ✅ `doctor2_context` fixture

### Correção 3: Corrigir Import do QuizTemplate

**Arquivo:** `tests/security/test_rls_policies.py:325`

```python
# Linha 325: Antes
from app.models.quiz_template import QuizTemplate

# Linha 325: Depois
from app.models.quiz import QuizTemplate
```

### Correção 4: Ajustar Fixture Conftest (Opcional)

**Se quiser manter nome `db_session` nos testes:**

**Arquivo:** `tests/conftest.py`

Adicionar alias:
```python
@pytest.fixture
async def db_session(async_db_session):
    """Alias for async_db_session to match test expectations"""
    return async_db_session
```

---

## 📝 Plano de Correção

### Opção A: Correção Mínima (Recomendado)

**1. Corrigir import do QuizTemplate:**
```bash
# Linha 325 de tests/security/test_rls_policies.py
# Trocar: from app.models.quiz_template import QuizTemplate
# Por: from app.models.quiz import QuizTemplate
```

**2. Atualizar TODOS os fixtures e testes para usar `async_db_session`:**
```python
# Substituir em TODO o arquivo:
# db_session → async_db_session
```

**Arquivos afetados:**
- `tests/security/test_rls_policies.py` (7 ocorrências)

**Tempo estimado:** 5 minutos

### Opção B: Correção Estrutural

**1. Renomear fixture no conftest:**
```python
# tests/conftest.py
@pytest.fixture
async def db_session(async_test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Async database session (renamed from async_db_session)"""
    async with async_test_engine.connect() as connection:
        # ... (mesmo código de async_db_session)
```

**2. Remover fixture sync antiga**

**3. Corrigir import QuizTemplate**

**Tempo estimado:** 10 minutos

---

## ✅ Checklist de Execução

**Para aplicar Opção A:**

- [ ] 1. Backup do arquivo: `cp tests/security/test_rls_policies.py tests/security/test_rls_policies.py.bak`
- [ ] 2. Corrigir linha 325: `from app.models.quiz import QuizTemplate`
- [ ] 3. Substituir `db_session` por `async_db_session` em:
  - [ ] Linha 20: `async def doctor1_context(async_db_session: AsyncSession):`
  - [ ] Linha 53: `async def doctor2_context(async_db_session: AsyncSession):`
  - [ ] Linha 80: `async def test_doctor_can_only_see_own_patients(async_db_session: AsyncSession, ...)`
  - [ ] Linha 155: `async def test_user_can_only_update_own_profile(async_db_session: AsyncSession):`
  - [ ] Linha 224: `async def test_medical_reports_isolated_by_doctor(async_db_session: AsyncSession, ...)`
  - [ ] Linha 319: `async def test_quiz_templates_accessible_to_authenticated_users(async_db_session: AsyncSession):`
  - [ ] Linha 362: `async def test_unauthenticated_access_denied(async_db_session: AsyncSession):`
- [ ] 4. Substituir todas as referências `db_session.` por `async_db_session.` dentro das funções
- [ ] 5. Executar testes: `pytest tests/security/test_rls_policies.py -v`
- [ ] 6. Verificar 5/5 testes passando ✅

---

## 🎯 Próximos Passos

### ✅ Completado
1. ✅ **Correções de código aplicadas** - Trocado para `async_db_session`
2. ✅ **Import do QuizTemplate corrigido** - Usando `app.models.quiz`
3. ✅ **Packages instalados** - `psycopg`, `asyncpg`
4. ✅ **1/5 testes passando** - `test_quiz_templates_accessible_to_authenticated_users`

### ⚠️ Imediato (BLOQUEADOR)
1. **Corrigir Schema Mismatch** - Adicionar `auth_provider` ENUM ao Supabase
   ```bash
   # Opção A: Via Supabase Dashboard
   # SQL Editor → Nova Query:
   CREATE TYPE auth_provider AS ENUM ('local', 'firebase', 'google', 'apple');
   ALTER TABLE users ADD COLUMN auth_provider auth_provider DEFAULT 'local';

   # Opção B: Via migration
   supabase migration create add_auth_provider_enum
   ```

2. **Verificar RLS Policy users_select** - Garantir que bloqueia acesso anônimo
   ```sql
   -- Verificar policy atual
   SELECT * FROM pg_policies WHERE tablename = 'users' AND policyname LIKE '%select%';
   ```

3. **Re-executar testes** após correções
   ```bash
   pytest tests/security/test_rls_policies.py -v --tb=short --no-cov
   ```

### Curto Prazo
4. **Adicionar mais testes RLS:**
   - `test_messages_isolated_by_doctor` - Mensagens isoladas por médico
   - `test_alerts_isolated_by_doctor` - Alertas isolados por médico
   - `test_flow_states_isolated` - Estados de fluxo isolados

5. **Integrar testes ao CI:**
   ```yaml
   # .github/workflows/rls-tests.yml
   name: RLS Security Tests
   on: [push, pull_request]
   jobs:
     rls-tests:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - name: Run RLS tests
           run: pytest tests/security/test_rls_policies.py -v
   ```

### Médio Prazo
6. **Adicionar testes E2E:**
   - Login como Dr. Silva → CRUD pacientes
   - Login como Dr. Santos → Verificar isolamento
   - Teste de performance com 1000+ registros

---

## 📈 Métricas de Qualidade

### Cobertura de Testes RLS
| Tabela | Política | Teste Implementado | Status | Bloqueador |
|--------|----------|-------------------|--------|------------|
| **patients** | SELECT own doctor | ✅ test_doctor_can_only_see_own_patients | ❌ ERROR | auth_provider missing |
| **users** | UPDATE own | ✅ test_user_can_only_update_own_profile | ❌ FAILED | auth_provider missing |
| **medical_reports** | SELECT own patients | ✅ test_medical_reports_isolated_by_doctor | ❌ ERROR | auth_provider missing |
| **quiz_templates** | SELECT authenticated | ✅ test_quiz_templates_accessible | ✅ **PASSED** | - |
| **(unauthenticated)** | Deny all access | ✅ test_unauthenticated_access_denied | ❌ FAILED | RLS policy issue |
| **quiz_sessions** | INSERT public | ❌ Não implementado | - | - |
| **messages** | SELECT own doctor | ❌ Não implementado | - | - |
| **alerts** | SELECT own doctor | ❌ Não implementado | - | - |
| **flow_states** | SELECT own doctor | ❌ Não implementado | - | - |

**Cobertura:** 5/9 cenários testados (56%)
**Taxa de Sucesso:** 1/5 testes passando (20%)

### Análise de Impacto

**Severidade:** 🔴 **ALTA**

**Impacto:**
- ❌ Schema divergente entre código Python e Supabase
- ❌ 80% dos testes RLS bloqueados por schema mismatch
- ⚠️ 1 teste passou, provando que framework funciona
- ❌ Possível falha na policy de bloqueio anônimo

**Risco:** Sem testes passando, não podemos garantir que:
1. ❌ Médicos veem apenas seus pacientes (teste bloqueado)
2. ❌ Usuários não podem editar dados de outros (teste bloqueado)
3. ❌ Relatórios médicos estão isolados (teste bloqueado)
4. ✅ Quiz templates são acessíveis (VALIDADO)
5. ❌ Acesso anônimo é bloqueado (FALHOU - possível bug RLS)

**Progresso:**
- ✅ Correções de código aplicadas (async, imports, packages)
- ✅ Framework de testes funcionando (1 teste passou)
- ❌ Schema sync pendente (bloqueador crítico)
- ❌ RLS policy review pendente (segurança)

**Recomendação:** 🚨 **BLOQUEAR DEPLOY ATÉ:**
1. Adicionar campo `auth_provider` ao banco Supabase
2. Verificar/corrigir policy `users_select_own`
3. Re-executar testes e validar 5/5 passando

---

## 🔍 Análise Técnica

### Problema de Arquitetura

**Inconsistência identificada:**
- `conftest.py` fornece DUAS fixtures:
  - `db_session` (sync)
  - `async_db_session` (async)
- Testes RLS usam `async def` mas chamam `db_session` (sync)
- Resultado: Runtime errors

**Solução arquitetural:**
```python
# Padronizar para ASYNC em todos os testes de segurança
# Motivo: RLS é testado em runtime, precisa de queries reais ao DB
```

### Evidências do Erro

**Traceback completo:**
```python
tests/security/test_rls_policies.py:34: in doctor1_context
    await db_session.commit()
E   TypeError: object NoneType can't be used in 'await' expression
```

**Causa:**
```python
# conftest.py linha 98
session = SessionLocal()  # ← Session sync
# session.commit() existe
# await session.commit() → NoneType (não existe método async)
```

---

## 📚 Referências

- **Documentação RLS:** `RELATORIO_REVISAO_RLS.md`
- **Schema Completo:** `SCHEMA_MASTER_COMPLETO.sql`
- **Banco de Dados:** `BANCO_DE_DADOS_COMPLETO.md`
- **Pytest Async:** https://pytest-asyncio.readthedocs.io/

---

## 🎓 Lições Aprendidas

1. ✅ **Sempre verificar tipo de fixture**: Async test precisa async fixture (CORRIGIDO)
2. ✅ **Importações devem seguir estrutura real**: `app.models.quiz` não `app.models.quiz_template` (CORRIGIDO)
3. ✅ **Testes de segurança são críticos**: Devem estar no CI/CD pipeline
4. ✅ **Nomenclatura consistente**: `db_session` pode causar confusão se existem versões sync/async (CORRIGIDO)
5. ⚠️ **Schema sync é fundamental**: Modelos Python devem refletir 100% o banco de dados (PENDENTE)
6. 🔍 **RLS policies precisam auditoria**: Verificar que policies bloqueiam corretamente acesso anônimo

---

## 📝 Resumo Executivo Final

### Status: ⚠️ **PARCIALMENTE IMPLEMENTADO**

**Conquistas:**
- ✅ Correções de código Python aplicadas (100%)
- ✅ Framework de testes RLS validado (1 teste passou)
- ✅ Dependências instaladas (`psycopg`, `asyncpg`)
- ✅ Documentação completa gerada

**Bloqueadores Críticos:**
1. 🚨 **Schema Mismatch**: Campo `auth_provider` não existe no Supabase
   - **Impacto:** 3/5 testes bloqueados
   - **Ação:** Criar migration ou remover do modelo

2. 🚨 **RLS Policy Issue**: Acesso anônimo não está sendo bloqueado
   - **Impacto:** Falha de segurança potencial
   - **Ação:** Auditar policy `users_select_own`

**Taxa de Sucesso:**
- **Testes:** 1/5 passando (20%)
- **Correções aplicadas:** 4/4 (100%)
- **Issues encontrados:** 2 críticos

**Próxima Ação Imediata:**
```sql
-- 1. Adicionar auth_provider ao Supabase
CREATE TYPE auth_provider AS ENUM ('local', 'firebase', 'google', 'apple');
ALTER TABLE users ADD COLUMN auth_provider auth_provider DEFAULT 'local';

-- 2. Verificar RLS users policy
SELECT * FROM pg_policies WHERE tablename = 'users';

-- 3. Re-executar testes
pytest tests/security/test_rls_policies.py -v --no-cov
```

---

**Gerado em:** 2025-10-02
**Última atualização:** 2025-10-02 (após correções)
**Próxima ação:** Sincronizar schema Supabase e re-testar
**Status atual:** 1/5 testes passando, 2 bloqueadores críticos
**Meta:** ✅ 5/5 testes passando
