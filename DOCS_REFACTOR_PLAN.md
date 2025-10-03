# Plano de Refatoração de Documentação - Clínica Oncológica v2

**Data**: 2025-10-02
**Status**: Em Execução
**Versão**: 1.0

## Objetivo

Eliminar duplicações, arquivar relatórios antigos, centralizar documentação canônica e estabelecer estrutura sustentável com CI de qualidade.

## Estrutura Alvo

```
clinica-oncologica-v02/
├── README.md (mapa do monorepo + ponteiros)
├── backend-hormonia/
│   ├── SCHEMA_MASTER_COMPLETO.sql (v2.1 - canônico)
│   └── docs/
│       ├── README.md (índice)
│       ├── api/
│       │   └── API.md
│       ├── security/
│       │   ├── rls/
│       │   │   ├── TESTES_RLS_API_GUIA.md (canônico)
│       │   │   └── runtime-validation.md
│       │   ├── FIREBASE_SECURITY.md
│       │   └── README.md
│       ├── db/
│       │   ├── BANCO_DE_DADOS_COMPLETO.md (canônico)
│       │   ├── migrations/
│       │   ├── reports/
│       │   └── README.md
│       ├── deployment/
│       │   ├── DEPLOYMENT.md
│       │   ├── ENVIRONMENT_VARIABLES.md
│       │   └── MIGRATIONS_GUIDE.md
│       ├── redis/
│       │   ├── REDIS_USAGE_GUIDE.md
│       │   └── REDIS_FINAL_STATUS.md
│       ├── monitoring/
│       │   └── QUERY_PERFORMANCE_MONITORING.md
│       ├── testing/
│       │   ├── QUIZ_E2E_TESTING_METRICS.md
│       │   └── README.md
│       └── incidents/
│           └── _archive/
├── frontend-hormonia/
│   └── docs/
│       ├── README.md
│       ├── architecture/
│       ├── components/
│       │   └── COMPONENTS_GUIDE.md
│       ├── auth/
│       │   └── MedicoAuthContext-Usage.md
│       ├── deployment/
│       │   └── DEPLOYMENT_GUIDE.md
│       ├── testing/
│       │   └── TESTING_GUIDE.md
│       └── incidents/
│           └── _archive/
└── quiz-mensal-interface/
    └── docs/
        ├── README.md
        ├── deployment/
        │   └── DEPLOYMENT_GUIDE.md
        ├── integration/
        ├── security/
        │   └── SECURITY_AUDIT.md
        └── incidents/
            └── _archive/
```

## Mapeamento de Ações

### Raiz do Repositório

#### Mover
- ✅ `BANCO_DE_DADOS_COMPLETO.md` → `backend-hormonia/docs/db/`
- ✅ `TESTES_RLS_API_GUIA.md` → `backend-hormonia/docs/security/rls/`

#### Arquivar (`backend-hormonia/docs/incidents/_archive/`)
- ✅ `RELATORIO_REVISAO_RLS.md`
- ✅ `RELATORIO_TESTES_RLS.md`
- ✅ `VERIFICACAO_IMPLEMENTACAO_RLS_API.md`
- ✅ `VALIDACAO_RLS_VIA_MCP.md`
- ✅ `RESUMO_CONSOLIDACAO_DB.md`
- ✅ `RELATORIO_DELECAO_SQL.md`
- ✅ `RELATORIO_FINAL_CONSOLIDACAO.md`
- ✅ `DATABASE_COMPLETE_REPORT.md`
- ✅ `ARQUIVOS_SQL_PARA_DELETAR.md`
- ✅ `PYTHON_313_MIGRATION_SUMMARY.md`
- ✅ `TESTES_RLS_RESULTADO_FINAL.md`
- ✅ `RESUMO_FINAL_COMPLETO.md`
- ✅ `DEPLOYMENT_STATUS.md`

#### Deletar
- ✅ `nul` (arquivo vazio)

### Backend (`backend-hormonia/`)

#### Manter (com reorganização)
- ✅ `SCHEMA_MASTER_COMPLETO.sql` (manter localização atual, referenciar de docs/db/)
- ✅ `docs/API.md` → `docs/api/API.md`
- ✅ `docs/AUTHENTICATION_GUIDE.md` → `docs/security/`
- ✅ `docs/QUIZ_E2E_TESTING_METRICS.md` → `docs/testing/`
- ✅ `docs/QUERY_PERFORMANCE_MONITORING.md` → `docs/monitoring/`
- ✅ `docs/deployment/*` (consolidar)
- ✅ `config/monitoring/grafana/README.md` (manter)
- ✅ `REDIS_FINAL_STATUS.md` → `docs/redis/`
- ✅ `REDIS_USAGE_GUIDE.md` → `docs/redis/`

#### Arquivar
- ✅ `docs/database-schema-complete.md` → deletar (inconsistente)
- ✅ `docs/MIGRATIONS_SUMMARY_20250929.md` → `docs/incidents/_archive/`
- ✅ `docs/MIGRATION_SUMMARY.md` → `docs/incidents/_archive/`
- ✅ `docs/ANTI_REPETITION_FIX_REPORT.md` → `docs/incidents/_archive/`
- ✅ `docs/ANTI_REPETITION_SUMMARY.md` → `docs/incidents/_archive/`
- ✅ `docs/MONITORING_REDIS_FIX_REPORT.md` → `docs/incidents/_archive/`
- ✅ `docs/router_registry_audit_report.md` → `docs/incidents/_archive/`
- ✅ `docs/SECURITY_ANALYSIS_REPORT.md` → `docs/incidents/_archive/`
- ✅ `docs/SECURITY_IMPLEMENTATION_SUMMARY.md` → `docs/incidents/_archive/`
- ✅ `docs/database-index-migrations-summary.md` → `docs/incidents/_archive/`
- ✅ `docs/schema-creation-summary.md` → `docs/incidents/_archive/`
- ✅ `docs/QUIZ_RESPONSE_SUMMARY.md` → `docs/incidents/_archive/`
- ✅ `docs/QUIZ_PUBLIC_API_FIXES.md` → `docs/incidents/_archive/`
- ✅ `docs/performance/OPTIMIZATION_RESULTS.md` → `docs/incidents/_archive/`
- ✅ `REDIS_LEGACY_REMOVAL_GUIDE.md` → `docs/redis/` (depois arquivar)
- ✅ `REDIS_MIGRATION_SUMMARY.md` → `docs/redis/` (depois arquivar)

#### Unificar/Deletar Duplicatas
- ✅ `docs/firebase-setup.md` vs `docs/FIREBASE_ENV_SETUP.md` → manter FIREBASE_ENV_SETUP.md, deletar firebase-setup.md

### Frontend (`frontend-hormonia/docs/`)

#### Manter
- ✅ `docs/TYPE_SYSTEM.md` → `docs/architecture/`
- ✅ `docs/components/COMPONENTS_GUIDE.md`
- ✅ `docs/testing/TESTING_GUIDE.md`
- ✅ `docs/deployment/DEPLOYMENT_GUIDE.md`
- ✅ `docs/MedicoAuthContext-Usage.md` → `docs/auth/`

#### Arquivar
- ✅ `docs/frontend/login-ux-review.md` → `docs/incidents/_archive/`
- ✅ `docs/firebase-migration-complete.md` → `docs/incidents/_archive/`

### Quiz Interface (`quiz-mensal-interface/docs/`)

#### Manter
- ✅ `docs/DEPLOYMENT_GUIDE.md` → `docs/deployment/`
- ✅ `docs/quiz-integration-report.md` → `docs/integration/`
- ✅ `docs/SECURITY_AUDIT.md` → `docs/security/`

#### Arquivar
- ✅ `docs/FRONTEND_FIXES_SUMMARY.md` → `docs/incidents/_archive/`

#### Unificar
- ✅ `docs/RAILWAY_DEPLOYMENT.md` → conteúdo para `docs/deployment/DEPLOYMENT_GUIDE.md`, deletar

## Fases de Execução

### Fase 1: Estrutura e Índices (✅ Em Execução)
- [x] Criar diretórios necessários
- [x] Criar README.md de índice em cada `docs/`
- [ ] Atualizar README.md raiz com mapa de documentação

### Fase 2: Move/Archive/Delete
- [ ] Mover arquivos canônicos
- [ ] Arquivar relatórios de incidentes
- [ ] Deletar duplicatas e arquivos obsoletos
- [ ] Atualizar links internos

### Fase 3: CI de Documentação
- [ ] Adicionar markdownlint-cli2
- [ ] Adicionar lychee (link checker)
- [ ] Workflow `.github/workflows/docs.yml`

### Fase 4: Readmes e Pointers
- [ ] Atualizar README.md raiz
- [ ] Atualizar links nos READMEs de subprojetos
- [ ] Validação final de links

## Convenções de Qualidade

### Header Padrão
```markdown
# Título do Documento

**Data**: YYYY-MM-DD
**Status**: Canônico | Arquivado | Deprecated
**Owner**: [Nome/Time]
**Última Atualização**: YYYY-MM-DD
```

### Nomeação
- ❌ Evitar datas no nome (usar CHANGELOG/versões internas)
- ✅ Pastas por domínio: `security/`, `db/`, `deployment/`
- ✅ Nomes descritivos em UPPER_SNAKE_CASE.md

### Língua
- Padrão: PT-BR (consistente com projeto)

### Categorização
- **Canônicos**: Guias atuais e referências (API, RLS runtime, DB master, Deploy)
- **Reports**: Mover para `incidents/_archive/`

## CI Workflow Proposto

```yaml
# .github/workflows/docs.yml
name: Documentation Quality

on:
  pull_request:
    paths:
      - '**.md'
      - 'docs/**'

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint Markdown
        uses: DavidAnson/markdownlint-cli2-action@v14

  links:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check Links
        uses: lycheeverse/lychee-action@v1
        with:
          args: --verbose --no-progress '**/*.md'
```

## Status de Execução

- **Fase 1**: ⏳ Em andamento
- **Fase 2**: ⏸️ Aguardando
- **Fase 3**: ⏸️ Aguardando
- **Fase 4**: ⏸️ Aguardando

---

**Próximos Passos Imediatos**:
1. Criar estrutura de diretórios
2. Criar arquivos README.md de índice
3. Mover documentação canônica
4. Arquivar relatórios de incidentes
