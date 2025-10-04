# 🗃️ Migrations - Explicação Completa

## O Que São Migrations?

**Migrations** são como um "histórico de versões" do banco de dados. Cada arquivo de migration representa uma mudança específica na estrutura do banco.

---

## 🎯 Analogia Simples

Imagine que você tem uma casa (banco de dados):

```
🏠 Versão 1: Casa com 2 quartos
📝 Migration 001: "Adicionar 1 quarto" → 🏠 Casa com 3 quartos
📝 Migration 002: "Adicionar garagem" → 🏠 Casa com 3 quartos + garagem
📝 Migration 003: "Reformar cozinha" → 🏠 Casa com 3 quartos + garagem + cozinha nova
```

Cada migration é uma "reforma" registrada, que pode ser aplicada em ordem.

---

## 🗂️ Suas Migrations Atuais

Você tem **8 migrations** no projeto:

### 1. `002_incremental_rls_rollout.sql` (11.5 KB)
**O que faz**: Implementa Row Level Security (RLS) básico
- Protege tabelas sensíveis (users, patients, etc.)
- Define quem pode ler/escrever em cada tabela
- **Exemplo**: Médicos só veem pacientes deles

### 2. `003_rls_phase2_write_policies.sql` (19.9 KB)
**O que faz**: Adiciona políticas de escrita (INSERT/UPDATE/DELETE)
- Controla quem pode modificar dados
- **Exemplo**: Pacientes não podem editar prontuários médicos

### 3. `20251002_add_auth_provider_enum.sql` (4 KB)
**O que faz**: Adiciona tipos de autenticação
```sql
CREATE TYPE auth_provider AS ENUM (
  'email',
  'google',
  'facebook',
  'apple'
);
```

### 4. `20251002_fix_rls_users_select.sql` (4.6 KB)
**O que faz**: Corrige bug nas políticas de leitura de usuários

### 5. `20251004_add_admin_rls_policies.sql` (14.8 KB)
**O que faz**: Adiciona políticas para administradores
- Admins podem ver tudo
- Médicos veem apenas seus pacientes
- Pacientes veem apenas seus dados

### 6. `20251004_add_foreign_key_cascade_rules.sql` (16.4 KB)
**O que faz**: Define regras de CASCADE (efeito em cadeia)
```sql
-- Exemplo: Se deletar um paciente, deleta todos os seus questionários
ALTER TABLE quiz_sessions
ADD CONSTRAINT fk_quiz_sessions_patient
FOREIGN KEY (patient_id) REFERENCES patients(id)
ON DELETE CASCADE;  -- 👈 Esta linha faz a mágica
```

### 7. `20251004_add_gin_indexes_jsonb.sql` (11 KB)
**O que faz**: Cria índices GIN para busca rápida em campos JSONB
```sql
-- Exemplo: Busca rápida em respostas de questionários
CREATE INDEX idx_quiz_responses_gin
ON quiz_sessions USING GIN (responses);
```
**Benefício**: Consultas 10-100x mais rápidas em campos JSON

### 8. `20251004_expand_message_type_enum.sql` (4.5 KB)
**O que faz**: Adiciona novos tipos de mensagem
```sql
ALTER TYPE message_type ADD VALUE 'reminder';
ALTER TYPE message_type ADD VALUE 'notification';
ALTER TYPE message_type ADD VALUE 'alert';
```

---

## 🤔 Por Que Preciso Executar no Railway?

### Situação Atual

```
┌─────────────────────────────────────┐
│ Seu Computador (Desenvolvimento)   │
│                                     │
│ ✅ Migrations JÁ APLICADAS          │
│ ✅ Banco tem todas as tabelas       │
│ ✅ Índices criados                  │
│ ✅ RLS policies ativas              │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Railway Postgres (Produção)         │
│                                     │
│ ❌ Migrations NÃO APLICADAS          │
│ ❌ Banco VAZIO ou desatualizado     │
│ ❌ Sem índices                      │
│ ❌ Sem RLS policies                 │
└─────────────────────────────────────┘
```

**Problema**: Seu código espera que as tabelas existam, mas o banco no Railway está vazio!

---

## 🚀 Como Executar Migrations no Railway?

### Opção 1: Via Supabase Dashboard (RECOMENDADO)

Você mencionou que usa **Supabase** como banco. Então o processo é:

```
1. Acesse: https://app.supabase.com
2. Selecione seu projeto
3. Vá em: SQL Editor (menu lateral)
4. Para cada migration, faça:
   - Abra o arquivo .sql no VS Code
   - Copie todo o conteúdo
   - Cole no SQL Editor
   - Clique em "Run" (▶️)
   - Verifique se executou sem erros
```

**Exemplo prático:**

```sql
-- 1. Abrir arquivo: 20251004_add_gin_indexes_jsonb.sql
-- 2. Copiar TODO o conteúdo
-- 3. Colar no Supabase SQL Editor
-- 4. Clicar em Run

-- Output esperado:
-- ✅ CREATE INDEX idx_quiz_responses_gin
-- ✅ CREATE INDEX idx_patient_metadata_gin
-- etc...
```

### Opção 2: Via CLI do Supabase

Se você tem o Supabase CLI instalado:

```bash
# 1. Fazer login
supabase login

# 2. Linkar com seu projeto
supabase link --project-ref seu-projeto-id

# 3. Aplicar migrations
supabase db push
```

### Opção 3: Via Script Python (Backend)

Você pode criar um endpoint administrativo no backend:

```python
# backend-hormonia/app/api/v1/admin.py (NOVO)
from fastapi import APIRouter, Depends
from sqlalchemy import text
import os

router = APIRouter()

@router.post("/run-migrations")
async def run_migrations(
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin)  # Apenas admins
):
    """
    Executa todas as migrations pendentes.
    ⚠️ USO ÚNICO: Executar apenas no primeiro deploy!
    """
    migrations_dir = "sql/migrations"

    # Listar arquivos em ordem
    migration_files = sorted(os.listdir(migrations_dir))

    results = []
    for filename in migration_files:
        if filename.endswith('.sql'):
            filepath = os.path.join(migrations_dir, filename)

            with open(filepath, 'r') as f:
                sql_content = f.read()

            try:
                # Executar SQL
                db.execute(text(sql_content))
                db.commit()
                results.append({
                    "file": filename,
                    "status": "✅ SUCCESS"
                })
            except Exception as e:
                results.append({
                    "file": filename,
                    "status": f"❌ ERROR: {str(e)}"
                })

    return {"migrations": results}
```

**Como usar:**
```bash
# Após deploy do backend no Railway:
curl -X POST https://backend-hormonia.railway.app/api/v1/admin/run-migrations \
  -H "Authorization: Bearer SEU_TOKEN_ADMIN"
```

---

## ⚠️ IMPORTANTE: Ordem de Execução

As migrations **DEVEM** ser executadas em ordem:

```
✅ CORRETO:
002 → 003 → 20251002_add_auth → 20251002_fix_rls → ...

❌ ERRADO:
20251004_add_gin → 002 → 003 → ...
```

**Por quê?**
- Migration 003 depende de tabelas criadas na 002
- Migration 20251004_add_gin depende de colunas criadas antes
- Executar fora de ordem = ERRO

---

## 🔍 Como Saber Se Já Foi Executada?

### Opção 1: Tabela de Controle (Supabase)

Supabase cria automaticamente uma tabela `schema_migrations`:

```sql
-- Verificar quais migrations já rodaram
SELECT * FROM schema_migrations;

-- Output:
-- version              | inserted_at
-- -------------------- | -------------------
-- 002                  | 2025-10-01 10:30:00
-- 003                  | 2025-10-01 10:31:00
-- 20251002_add_auth    | 2025-10-02 14:00:00
```

### Opção 2: Verificar Manualmente

```sql
-- Verificar se índice GIN existe
SELECT indexname
FROM pg_indexes
WHERE indexname = 'idx_quiz_responses_gin';

-- Se retornar vazio = Migration 7 NÃO foi aplicada
-- Se retornar 1 linha = Migration 7 JÁ foi aplicada
```

---

## 📊 Resumo: O Que Você Precisa Fazer

### Passo a Passo Simples

```
┌─────────────────────────────────────────────────────┐
│ 1️⃣ DEPLOY DO BACKEND NO RAILWAY                     │
│    - Código Python sobe para Railway               │
│    - Backend fica disponível                        │
│    - MAS banco ainda está vazio                     │
└─────────────────────────────────────────────────────┘
                         ⬇️
┌─────────────────────────────────────────────────────┐
│ 2️⃣ EXECUTAR MIGRATIONS NO SUPABASE                  │
│    - Acesse Supabase Dashboard                      │
│    - SQL Editor                                     │
│    - Copie/cole cada .sql em ordem                  │
│    - Run em cada um                                 │
│    - Verifique erros                                │
└─────────────────────────────────────────────────────┘
                         ⬇️
┌─────────────────────────────────────────────────────┐
│ 3️⃣ VALIDAR QUE DEU CERTO                            │
│    - Teste o endpoint /health                       │
│    - Tente criar um usuário                         │
│    - Verifique se RLS funciona                      │
└─────────────────────────────────────────────────────┘
```

---

## 💡 Dica: Automação Futura

Para evitar executar manualmente, você pode:

1. **Usar Supabase CLI no CI/CD**:
```yaml
# .github/workflows/deploy.yml
- name: Run migrations
  run: |
    supabase link --project-ref ${{ secrets.SUPABASE_PROJECT_ID }}
    supabase db push
```

2. **Criar script de inicialização**:
```python
# backend-hormonia/app/core/startup.py
async def run_migrations_on_startup():
    """
    Verifica e aplica migrations automaticamente
    ⚠️ Cuidado em produção: pode causar downtime
    """
    pass
```

---

## 🎓 Entendeu?

**Resumo em 1 frase:**

> Migrations são arquivos SQL que criam/modificam tabelas no banco. Você executou elas no seu computador, mas precisa executar de novo no Supabase (Railway Postgres) para que as tabelas existam lá também.

**Analogia final:**

```
Seu código = Receita de bolo
Migrations = Comprar ingredientes

✅ Você tem a receita (código)
❌ Mas a cozinha do Railway está vazia (sem ingredientes/tabelas)

Solução: Executar migrations = Comprar ingredientes para a cozinha do Railway
```

---

**Tem alguma dúvida específica sobre alguma migration?**
