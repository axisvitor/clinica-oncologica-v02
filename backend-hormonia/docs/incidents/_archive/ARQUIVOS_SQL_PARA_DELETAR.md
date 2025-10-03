# Arquivos SQL Redundantes - Recomendações de Deleção

**Data:** 2025-10-02
**Análise:** Identificação de arquivos SQL duplicados, obsoletos ou consolidados

---

## 📋 Resumo

Após consolidação completa do banco de dados:
- ✅ **Documento master criado:** `BANCO_DE_DADOS_COMPLETO.md` (documentação)
- ✅ **Schema master criado:** `backend-hormonia/SCHEMA_MASTER_COMPLETO.sql` (SQL consolidado)
- 📦 **Total de arquivos SQL encontrados:** 14 arquivos
- 🗑️ **Arquivos recomendados para deleção:** 8 arquivos

---

## 🗂️ Arquivos SQL Encontrados

### Localização dos Arquivos

```
backend-hormonia/
├── init-db.sql                                          ❌ DELETAR
├── migrations/
│   ├── 001_create_admin_tables.sql                      ❌ DELETAR
│   ├── 001_create_admin_users.sql                       ❌ DELETAR
│   ├── 002_cleanup_test_data.sql                        ⚠️  MANTER (útil)
│   ├── fix_user_role_enum.sql                           ❌ DELETAR
│   └── supabase_admin_system_complete.sql               ⚠️  AVALIAR
├── seeds/
│   ├── 001_admin_permissions.sql                        ⚠️  MANTER (dados)
│   └── 001_admin_roles_seed.sql                         ⚠️  MANTER (dados)
├── sql/
│   ├── migrations/
│   │   ├── 002_incremental_rls_rollout.sql              ⚠️  MANTER (referência)
│   │   └── 003_rls_phase2_write_policies.sql            ⚠️  MANTER (referência)
│   ├── migrations-archive/
│   │   └── 002_incremental_rls_rollout.sql              ❌ DELETAR
│   └── monitoring/
│       └── rls_monitoring_dashboard.sql                 ⚠️  MANTER (útil)
├── alembic/versions/
│   └── 20250929_193000_add_performance_indexes.sql      ⚠️  MANTER (Alembic)
└── app/migrations/
    └── add_audit_actor_subject_fields.sql               ❌ DELETAR
```

---

## ❌ Arquivos Recomendados para DELEÇÃO (8 arquivos)

### 1. `init-db.sql` (Raiz do backend-hormonia)

**Motivo:**
- Schema legacy básico (apenas 8 tabelas)
- Substituído por 54 migrações do Supabase
- Estrutura desatualizada
- **CONSOLIDADO EM:** `SCHEMA_MASTER_COMPLETO.sql`

**Impacto:** Nenhum (não é usado em produção)

**Comando:**
```bash
rm backend-hormonia/init-db.sql
```

---

### 2. `migrations/001_create_admin_tables.sql`

**Motivo:**
- Migration antiga/duplicada
- Substituída por `supabase_admin_system_complete.sql`
- Não está no histórico oficial de migrations do Supabase

**Impacto:** Nenhum (migration obsoleta)

**Comando:**
```bash
rm backend-hormonia/migrations/001_create_admin_tables.sql
```

---

### 3. `migrations/001_create_admin_users.sql`

**Motivo:**
- Duplicata de migration
- Mesmo propósito que arquivo #2
- Não está no histórico oficial

**Impacto:** Nenhum

**Comando:**
```bash
rm backend-hormonia/migrations/001_create_admin_users.sql
```

---

### 4. `migrations/fix_user_role_enum.sql`

**Motivo:**
- Fix pontual já aplicado
- Substituído por migrations mais recentes
- Remoção de role 'nurse' (já feito)

**Impacto:** Nenhum (fix já aplicado)

**Comando:**
```bash
rm backend-hormonia/migrations/fix_user_role_enum.sql
```

---

### 5. `sql/migrations-archive/002_incremental_rls_rollout.sql`

**Motivo:**
- Arquivo arquivado (duplicata)
- Versão atual está em `sql/migrations/`
- Não deve estar em produção

**Impacto:** Nenhum (arquivo de arquivo)

**Comando:**
```bash
rm backend-hormonia/sql/migrations-archive/002_incremental_rls_rollout.sql
# Ou deletar toda a pasta migrations-archive se vazia
rmdir backend-hormonia/sql/migrations-archive
```

---

### 6. `app/migrations/add_audit_actor_subject_fields.sql`

**Motivo:**
- Migration solta não gerenciada
- Alteração já aplicada (colunas actor_subject existem)
- Não é Alembic nem Supabase migration

**Impacto:** Nenhum

**Comando:**
```bash
rm backend-hormonia/app/migrations/add_audit_actor_subject_fields.sql
# Se a pasta app/migrations ficar vazia:
rmdir backend-hormonia/app/migrations
```

---

### 7-8. OPCIONAL: `migrations/supabase_admin_system_complete.sql`

**Motivo:**
- Migration gigante monolítica (783 linhas)
- Substituída por múltiplas migrations incrementais no Supabase
- Pode ser útil para referência, mas não deve ser executada

**Decisão:** ⚠️ **AVALIAR** - Pode manter como referência ou deletar

**Se deletar:**
```bash
rm backend-hormonia/migrations/supabase_admin_system_complete.sql
```

---

## ⚠️ Arquivos para MANTER (Úteis)

### Seeds (Dados Iniciais)

```
✅ backend-hormonia/seeds/001_admin_permissions.sql
✅ backend-hormonia/seeds/001_admin_roles_seed.sql
```

**Motivo:** Contêm dados seed importantes (permissions, roles)

---

### Migrations de Referência

```
✅ backend-hormonia/sql/migrations/002_incremental_rls_rollout.sql
✅ backend-hormonia/sql/migrations/003_rls_phase2_write_policies.sql
```

**Motivo:** RLS policies bem documentadas, úteis como referência

---

### Monitoring

```
✅ backend-hormonia/sql/monitoring/rls_monitoring_dashboard.sql
```

**Motivo:** Queries úteis para monitoramento de RLS

---

### Cleanup Utility

```
✅ backend-hormonia/migrations/002_cleanup_test_data.sql
```

**Motivo:** Script útil para limpar dados de teste

---

### Alembic

```
✅ backend-hormonia/alembic/versions/*.sql
```

**Motivo:** Migrations gerenciadas pelo Alembic (Python backend)

---

## 📦 Comandos de Deleção Consolidados

### Deleção Segura (Recomendado)

```bash
cd backend-hormonia

# Arquivos definitivamente obsoletos
rm init-db.sql
rm migrations/001_create_admin_tables.sql
rm migrations/001_create_admin_users.sql
rm migrations/fix_user_role_enum.sql
rm app/migrations/add_audit_actor_subject_fields.sql

# Arquivo arquivado
rm sql/migrations-archive/002_incremental_rls_rollout.sql

# Limpar pastas vazias
rmdir app/migrations 2>/dev/null || true
rmdir sql/migrations-archive 2>/dev/null || true
```

### Deleção Agressiva (Opcional)

Se quiser remover também o arquivo monolítico:

```bash
# Adicional
rm migrations/supabase_admin_system_complete.sql
```

---

## 🔍 Estrutura Final Recomendada

```
backend-hormonia/
├── SCHEMA_MASTER_COMPLETO.sql          ← NOVO: Schema consolidado completo
├── seeds/                               ← MANTER: Dados iniciais
│   ├── 001_admin_permissions.sql
│   └── 001_admin_roles_seed.sql
├── sql/
│   ├── migrations/                      ← MANTER: Migrations de referência
│   │   ├── 002_incremental_rls_rollout.sql
│   │   └── 003_rls_phase2_write_policies.sql
│   └── monitoring/                      ← MANTER: Queries de monitoring
│       └── rls_monitoring_dashboard.sql
├── alembic/versions/                    ← MANTER: Migrations Alembic (Python)
│   └── *.py
└── migrations/                          ← MANTER: Cleanup script
    └── 002_cleanup_test_data.sql
```

**Total de arquivos removidos:** 6-8 arquivos
**Espaço recuperado:** ~100 KB
**Benefício:** Estrutura mais limpa e organizada

---

## ✅ Checklist de Execução

Antes de deletar, verifique:

- [ ] Nenhum script CI/CD referencia esses arquivos
- [ ] Nenhum Docker Compose usa `init-db.sql`
- [ ] README não menciona esses arquivos
- [ ] Nenhum desenvolvedor depende desses arquivos localmente

Depois de deletar:

- [ ] Commit as mudanças
- [ ] Atualizar documentação se necessário
- [ ] Avisar equipe sobre arquivos removidos

---

## 📝 Commit Sugerido

```bash
git rm backend-hormonia/init-db.sql
git rm backend-hormonia/migrations/001_create_admin_tables.sql
git rm backend-hormonia/migrations/001_create_admin_users.sql
git rm backend-hormonia/migrations/fix_user_role_enum.sql
git rm backend-hormonia/app/migrations/add_audit_actor_subject_fields.sql
git rm backend-hormonia/sql/migrations-archive/002_incremental_rls_rollout.sql

git commit -m "chore: remove arquivos SQL obsoletos e duplicados

- Remove init-db.sql (legacy schema)
- Remove migrations obsoletas não aplicadas
- Remove arquivos arquivados duplicados
- Mantém seeds, monitoring e migrations de referência
- Estrutura consolidada em SCHEMA_MASTER_COMPLETO.sql"
```

---

## 🎯 Próximos Passos

1. **Revisar lista** de arquivos a deletar
2. **Backup** (opcional, já está no Git)
3. **Executar comandos** de deleção
4. **Testar** que nada quebrou
5. **Commit** e push

---

## 📞 Dúvidas?

Se não tiver certeza sobre algum arquivo, **MANTENHA** até confirmar que não é usado.

**Regra de ouro:** Se houver dúvida, não delete. Melhor ter arquivos extras do que perder algo importante.

---

**Gerado em:** 2025-10-02
**Status:** ✅ Pronto para revisão e execução
