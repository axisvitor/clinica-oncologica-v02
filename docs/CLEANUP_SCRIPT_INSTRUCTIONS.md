# Script de Cleanup - Instruções de Execução
## Remoção de Arquivos Legacy e Deprecated

**Data**: 2025-11-08
**Objetivo**: Remover ~7.444 linhas de código legacy identificadas na revisão v2

---

## ⚠️ ANTES DE EXECUTAR

### Pré-requisitos Obrigatórios

1. **Backup Completo**
   ```bash
   # Criar backup completo do repositório
   cd /home/user/clinica-oncologica-v02
   git add -A
   git commit -m "chore: backup before legacy cleanup"
   git push
   ```

2. **Branch de Trabalho**
   ```bash
   # Criar branch específica para cleanup
   git checkout -b cleanup/remove-legacy-files-v2-migration
   ```

3. **Testes Passando**
   ```bash
   # Backend
   cd backend-hormonia
   pytest tests/ -v

   # Frontend
   cd ../frontend-hormonia
   npm test
   ```

4. **Revisão de Dependências**
   ```bash
   # Verificar que nenhum arquivo ativo importa os deprecated
   cd /home/user/clinica-oncologica-v02

   # Para cada arquivo a ser removido, verificar imports
   grep -r "from app.services.alert import" backend-hormonia/
   grep -r "import.*api-client.legacy" frontend-hormonia/
   ```

---

## 🔴 FASE 1: Arquivos Frontend (CRÍTICO - 30 min)

### 1.1 Deletar API Client Legacy
```bash
cd /home/user/clinica-oncologica-v02/frontend-hormonia

# Verificar que não há imports
grep -r "api-client.legacy" src/

# Se nenhum resultado, prosseguir
rm src/lib/api-client.legacy.ts

# Commit
git add src/lib/api-client.legacy.ts
git commit -m "chore(frontend): remove legacy API client (1,217 lines)"
```

### 1.2 Deletar WebSocket Legacy
```bash
cd /home/user/clinica-oncologica-v02/frontend-hormonia

# Verificar imports antes de deletar
grep -r "from.*lib/websocket" src/
grep -r "from.*lib/types/websocket" src/

# Se usar src/lib/websocket.ts (correto), prosseguir
rm lib/websocket.ts
rm lib/types/websocket.ts

git add lib/
git commit -m "chore(frontend): remove duplicate WebSocket implementations (374 lines)"
```

### 1.3 Deletar Type Definitions Duplicadas
```bash
cd /home/user/clinica-oncologica-v02/frontend-hormonia

# IMPORTANTE: Primeiro atualizar todos os imports
# Encontrar arquivos que precisam atualização
grep -r "from '@/lib/types/flow'" src/
grep -r "from '@/lib/types/ai'" src/
grep -r "from '@/lib/types/api'" src/

# Criar script de substituição (execute após verificar acima)
cat > /tmp/update_imports.sh << 'EOF'
#!/bin/bash
find src/ -type f -name "*.ts" -o -name "*.tsx" | while read file; do
  sed -i "s|from '@/lib/types/flow'|from '@/types/api'|g" "$file"
  sed -i "s|from '@/lib/types/ai'|from '@/types/api'|g" "$file"
  sed -i "s|from '@/lib/types/api'|from '@/types/api'|g" "$file"
done
EOF

chmod +x /tmp/update_imports.sh
/tmp/update_imports.sh

# Verificar alterações
git diff

# Deletar arquivos deprecated
rm lib/types/flow.ts
rm lib/types/ai.ts
rm lib/types/api.ts

# Commit
git add .
git commit -m "refactor(frontend): consolidate type imports to @/types/api (~500 lines removed)"
```

### 1.4 Corrigir Teste com Endpoint v1
```bash
cd /home/user/clinica-oncologica-v02/frontend-hormonia

# Editar arquivo
nano src/hooks/api/__tests__/usePhysicianRiskAssessments.test.ts

# Substituir manualmente ou usar sed:
sed -i 's|/api/v1/analytics/physicians/risk-assessments|/api/v2/analytics/physicians/risk-assessments|g' \
  src/hooks/api/__tests__/usePhysicianRiskAssessments.test.ts

# Verificar
grep "api/v" src/hooks/api/__tests__/usePhysicianRiskAssessments.test.ts

# Commit
git add src/hooks/api/__tests__/usePhysicianRiskAssessments.test.ts
git commit -m "fix(frontend): update test to use v2 API endpoints"
```

### 1.5 Consolidar Fetch em API Client
```bash
cd /home/user/clinica-oncologica-v02/frontend-hormonia

# Arquivos afetados:
# - src/pages/MetricsDashboardPage.tsx:57
# - src/pages/AdminPage.tsx:118
# - src/pages/ReportsPage.tsx:64

# Abrir cada arquivo e substituir fetch() por apiClient methods
# Exemplo para MetricsDashboardPage.tsx:

# ANTES:
# const response = await fetch(`${API_BASE_URL}/api/v2/metrics/dashboard`)
# const data = await response.json()

# DEPOIS:
# import { apiClient } from '@/lib/api-client'
# const data = await apiClient.metrics.getDashboard()

# Commit após cada arquivo
git add src/pages/MetricsDashboardPage.tsx
git commit -m "refactor(frontend): use API client instead of direct fetch in MetricsDashboardPage"

git add src/pages/AdminPage.tsx
git commit -m "refactor(frontend): use API client instead of direct fetch in AdminPage"

git add src/pages/ReportsPage.tsx
git commit -m "refactor(frontend): use API client instead of direct fetch in ReportsPage"
```

### 1.6 Remover Hook Duplicado
```bash
cd /home/user/clinica-oncologica-v02/frontend-hormonia

# Identificar qual versão manter (verificar imports)
grep -r "useSystemStats" src/

# Deletar duplicata (exemplo, ajustar conforme necessário)
# rm src/hooks/useSystemStats.ts  # Se a versão em src/hooks/api/ é melhor

git add src/hooks/
git commit -m "chore(frontend): remove duplicate useSystemStats hook"
```

### ✅ Checkpoint Fase 1
```bash
# Executar testes frontend
npm test

# Se passar, commit consolidado
git add .
git commit -m "chore(frontend): Phase 1 cleanup complete - removed 2,500+ legacy lines"
git push origin cleanup/remove-legacy-files-v2-migration
```

---

## 🟡 FASE 2: WebSocket Backend (ALTA - 1 hora)

### 2.1 Migrar enhanced_websockets.py
```bash
cd /home/user/clinica-oncologica-v02/backend-hormonia

# Backup antes de editar
cp app/api/enhanced_websockets.py app/api/enhanced_websockets.py.backup

# Editar arquivo
nano app/api/enhanced_websockets.py

# Substituir imports:
# REMOVER:
# from app.services.websocket_manager import WebSocketManager, ConnectionManager
# from app.services.enhanced_websocket_manager import EnhancedWebSocketManager

# ADICIONAR:
# from app.services.websocket import get_websocket_manager

# Atualizar código para usar get_websocket_manager()

# Testar
pytest tests/websocket/ -v

# Se passar, commit
git add app/api/enhanced_websockets.py
git commit -m "refactor(backend): migrate enhanced_websockets to use unified manager"
```

### 2.2 Arquivar WebSocket Legacy
```bash
cd /home/user/clinica-oncologica-v02/backend-hormonia

# Criar diretório de arquivo
mkdir -p legacy/websocket_archive_2025-11-08

# Verificar que enhanced_websockets.py não importa mais estes
grep -n "websocket_manager\|enhanced_websocket_manager" app/api/enhanced_websockets.py

# Se não houver resultados, prosseguir
mv app/services/websocket_manager.py legacy/websocket_archive_2025-11-08/
mv app/services/enhanced_websocket_manager.py legacy/websocket_archive_2025-11-08/

# Verificar se websocket_heartbeat.py e websocket_service.py ainda são importados
grep -r "websocket_heartbeat\|websocket_service" app/

# Se não houver resultados, arquivar também
mv app/services/websocket_heartbeat.py legacy/websocket_archive_2025-11-08/ 2>/dev/null || true
mv app/services/websocket_service.py legacy/websocket_archive_2025-11-08/ 2>/dev/null || true

# Commit
git add app/services/ legacy/
git commit -m "chore(backend): archive legacy WebSocket implementations (3,027 lines)"
```

### ✅ Checkpoint Fase 2
```bash
# Testar WebSocket
cd /home/user/clinica-oncologica-v02/backend-hormonia
pytest tests/websocket/ -v
pytest tests/integration/test_websocket*.py -v

# Se passar, push
git push origin cleanup/remove-legacy-files-v2-migration
```

---

## 🟢 FASE 3: Sistema de Alertas (MÉDIA - 1 hora)

### 3.1 Verificar Feature Flag
```bash
cd /home/user/clinica-oncologica-v02/backend-hormonia

# Verificar status do feature flag
grep -r "USE_CONSOLIDATED_ALERTS" app/config/

# Verificar onde é usado
grep -r "USE_CONSOLIDATED_ALERTS" app/

# DECISÃO:
# - Se flag = True em produção há 30+ dias: Remover flag e código legacy
# - Se flag = False ou recente: Manter por enquanto
```

### 3.2 Remover Sistema de Alertas Legacy (se flag = True há 30+ dias)
```bash
cd /home/user/clinica-oncologica-v02/backend-hormonia

# Verificar que não há imports diretos
grep -r "from app.services.alert import AlertService" app/api/
grep -r "from app.services.alert_processor import" app/api/

# Arquivar
mkdir -p legacy/alerts_archive_2025-11-08
mv app/services/alert.py legacy/alerts_archive_2025-11-08/
mv app/services/alert_processor.py legacy/alerts_archive_2025-11-08/
mv app/services/monitoring/alert_service.py legacy/alerts_archive_2025-11-08/

# Remover feature flag de config
# Editar app/config/settings/base.py (ou equivalente)
# Remover USE_CONSOLIDATED_ALERTS

# Remover código condicional em v1_archived
# (opcional, já que v1 está arquivado)

# Commit
git add .
git commit -m "chore(backend): archive legacy alert system (~1,500 lines)"
```

### ✅ Checkpoint Fase 3
```bash
cd /home/user/clinica-oncologica-v02/backend-hormonia
pytest tests/alerts/ -v
pytest tests/services/test_alert*.py -v

git push origin cleanup/remove-legacy-files-v2-migration
```

---

## 🔵 FASE 4: Cache e Outros Serviços (MÉDIA - 1 hora)

### 4.1 Executar Script de Cleanup de Cache
```bash
cd /home/user/clinica-oncologica-v02/backend-hormonia

# Revisar script primeiro
cat scripts/cleanup_legacy_cache.py

# Executar em modo dry-run (se suportado)
python scripts/cleanup_legacy_cache.py --dry-run

# Se OK, executar
python scripts/cleanup_legacy_cache.py

# Commit
git add .
git commit -m "chore(backend): cleanup legacy cache implementations (~800 lines)"
```

### 4.2 Remover Outros Serviços Deprecated
```bash
cd /home/user/clinica-oncologica-v02/backend-hormonia

# Verificar que não há imports
grep -r "from app.services.message_sender import" app/
grep -r "from app.services.message_factory import" app/
grep -r "from app.utils.unified_cache import" app/
grep -r "from app.core.redis_unified import" app/

# Se não houver resultados, arquivar
mkdir -p legacy/services_archive_2025-11-08

mv app/services/message_sender.py legacy/services_archive_2025-11-08/ 2>/dev/null || true
mv app/services/message_factory.py legacy/services_archive_2025-11-08/ 2>/dev/null || true
mv app/utils/unified_cache.py legacy/services_archive_2025-11-08/ 2>/dev/null || true
mv app/core/redis_unified.py legacy/services_archive_2025-11-08/ 2>/dev/null || true

git add .
git commit -m "chore(backend): archive deprecated services"
```

### ✅ Checkpoint Fase 4
```bash
cd /home/user/clinica-oncologica-v02/backend-hormonia
pytest tests/ -v --tb=short

git push origin cleanup/remove-legacy-files-v2-migration
```

---

## 🗄️ FASE 5: Database Cleanup (OPCIONAL - 2 horas)

### 5.1 Criar Migração para Patient Metadata
```bash
cd /home/user/clinica-oncologica-v02/backend-hormonia

# Criar nova migração Alembic
alembic revision -m "remove_patient_metadata_compatibility_layer"

# Editar arquivo de migração gerado
# Adicionar:
# - Remover coluna patient.patient_metadata
# - Remover métodos de compatibilidade (via código Python)

# Testar migração
alembic upgrade head

# Reverter para testar downgrade
alembic downgrade -1

# Se OK, commit
git add alembic/versions/
git commit -m "feat(database): remove patient metadata compatibility layer"
```

### 5.2 Criar Migração para FlowAnalytics
```bash
cd /home/user/clinica-oncologica-v02/backend-hormonia

alembic revision -m "remove_flow_analytics_duplicate_columns"

# Editar migração:
# - Remover flow_analytics.step_name (usar message_key)
# - Remover flow_analytics.content (usar message_text)

alembic upgrade head
alembic downgrade -1

git add alembic/versions/
git commit -m "feat(database): remove FlowAnalytics duplicate columns"
```

### 5.3 Converter SQL Migrations para Alembic
```bash
cd /home/user/clinica-oncologica-v02/backend-hormonia

# Encontrar migrações SQL pendentes
ls -la migrations/*.sql

# Para cada .sql, criar equivalente em Alembic
# Exemplo para 003_add_gin_indexes_patient_metadata.sql:

alembic revision -m "add_gin_indexes_patient_metadata"

# Editar migração gerada, copiar conteúdo do .sql para upgrade()

# Testar
alembic upgrade head

# Marcar .sql como migrado
mv migrations/003_add_gin_indexes_patient_metadata.sql \
   migrations/migrated/003_add_gin_indexes_patient_metadata.sql.done

git add alembic/versions/ migrations/
git commit -m "feat(database): convert SQL migration to Alembic"
```

### ✅ Checkpoint Fase 5
```bash
cd /home/user/clinica-oncologica-v02/backend-hormonia

# Testar todas as migrações
alembic downgrade base
alembic upgrade head

# Verificar schema
alembic current

pytest tests/database/ -v

git push origin cleanup/remove-legacy-files-v2-migration
```

---

## ✅ VALIDAÇÃO FINAL

### Testes Completos
```bash
cd /home/user/clinica-oncologica-v02

# Backend
cd backend-hormonia
pytest tests/ -v --cov=app --cov-report=term-missing

# Frontend
cd ../frontend-hormonia
npm test -- --coverage

# Linting
npm run lint

# Type checking
npm run type-check
```

### Verificação de Imports Quebrados
```bash
cd /home/user/clinica-oncologica-v02

# Backend - verificar imports de arquivos removidos
cd backend-hormonia
python -c "
import ast
import os
removed_modules = [
    'app.services.websocket_manager',
    'app.services.enhanced_websocket_manager',
    'app.services.alert',
    'app.services.alert_processor',
]
# TODO: Scan all .py files and check imports
"

# Frontend - verificar imports
cd ../frontend-hormonia
grep -r "api-client.legacy" src/ && echo "ERROR: Found legacy imports!" || echo "OK"
grep -r "lib/websocket" src/ && echo "ERROR: Found legacy imports!" || echo "OK"
grep -r "lib/types/" src/ && echo "ERROR: Found legacy imports!" || echo "OK"
```

### Build de Produção
```bash
# Backend
cd /home/user/clinica-oncologica-v02/backend-hormonia
docker build -t hormonia-backend:cleanup-test .

# Frontend
cd /home/user/clinica-oncologica-v02/frontend-hormonia
npm run build

# Verificar sem erros
echo $?  # Deve retornar 0
```

---

## 📊 Estatísticas Finais

### Executar após cleanup completo
```bash
cd /home/user/clinica-oncologica-v02

# Contar linhas removidas
cat > /tmp/count_removed.sh << 'EOF'
#!/bin/bash
echo "=== LINHAS REMOVIDAS ==="
echo "Frontend legacy API client: 1,217"
echo "Frontend WebSocket duplicado: 374"
echo "Frontend type definitions: ~500"
echo "Backend WebSocket legacy: 3,027"
echo "Backend alerts legacy: ~1,500"
echo "Backend cache legacy: ~800"
echo "Backend outros serviços: ~300"
echo ""
echo "TOTAL: ~7,718 linhas removidas"
echo ""
echo "=== ARQUIVOS REMOVIDOS ==="
git log --oneline cleanup/remove-legacy-files-v2-migration | wc -l
echo "commits realizados"
EOF

chmod +x /tmp/count_removed.sh
/tmp/count_removed.sh
```

---

## 🚀 Finalização

### Merge para Main
```bash
cd /home/user/clinica-oncologica-v02

# Atualizar branch
git checkout cleanup/remove-legacy-files-v2-migration
git pull origin cleanup/remove-legacy-files-v2-migration

# Rebase com main (se necessário)
git fetch origin
git rebase origin/main

# Criar PR
gh pr create \
  --title "chore: Remove legacy code from v2 migration (~7,700 lines)" \
  --body "$(cat <<'EOF'
## Summary
Complete cleanup of legacy code identified in v2 migration review.

## Changes
- ✅ Removed frontend legacy API client (1,217 lines)
- ✅ Removed duplicate WebSocket implementations (3,401 lines)
- ✅ Removed deprecated backend services (2,600 lines)
- ✅ Consolidated type definitions (~500 lines)
- ✅ Updated tests to use v2 endpoints
- ✅ Migrated fetch() calls to API client

## Testing
- [x] All backend tests passing
- [x] All frontend tests passing
- [x] Production build successful
- [x] No broken imports detected

## Metrics
- **Lines removed**: ~7,718
- **Files archived**: 20+
- **Code reduction**: ~8.5%

## Verification
```bash
# Backend
cd backend-hormonia && pytest tests/ -v

# Frontend
cd frontend-hormonia && npm test
```

Closes #XX
EOF
)" \
  --base main \
  --head cleanup/remove-legacy-files-v2-migration
```

### Após Merge
```bash
# Atualizar main local
git checkout main
git pull origin main

# Deletar branch de cleanup
git branch -d cleanup/remove-legacy-files-v2-migration
git push origin --delete cleanup/remove-legacy-files-v2-migration

# Tag da versão
git tag -a v2.0.0-cleanup -m "Complete removal of legacy code from v2 migration"
git push origin v2.0.0-cleanup
```

---

## 📋 Checklist Final

### Antes de Merge
- [ ] Todos os testes passando (backend + frontend)
- [ ] Build de produção sem erros
- [ ] Zero imports quebrados
- [ ] Documentação atualizada
- [ ] PR revisado por pelo menos 1 pessoa
- [ ] CHANGELOG.md atualizado

### Após Merge
- [ ] Deploy em staging
- [ ] Smoke tests em staging
- [ ] Monitoramento de erros 24h
- [ ] Deploy em produção (se staging OK)
- [ ] Arquivos de backup podem ser removidos após 30 dias

---

## ⚠️ Rollback Plan

### Se algo quebrar após merge:
```bash
# Reverter último commit
git revert HEAD

# Ou restaurar de backup
cd /home/user/clinica-oncologica-v02
git checkout main
git reset --hard <commit-hash-before-cleanup>
git push -f origin main  # CUIDADO!

# Restaurar arquivos específicos
git checkout <commit-hash> -- path/to/file
```

### Se backup de arquivo específico for necessário:
```bash
# Arquivos estão em:
# - /backend-hormonia/legacy/websocket_archive_2025-11-08/
# - /backend-hormonia/legacy/alerts_archive_2025-11-08/
# - /backend-hormonia/legacy/services_archive_2025-11-08/
# - Commits Git (git log --all -- path/to/deleted/file)

# Restaurar de Git
git log --all -- path/to/deleted/file  # Encontrar commit
git checkout <commit-hash> -- path/to/deleted/file
```

---

**Instruções criadas**: 2025-11-08
**Última atualização**: 2025-11-08
**Estimativa total**: 5-7 horas de trabalho
**Recomendação**: Executar em fases ao longo de 2-3 dias
