# 🚀 RLS DEPLOYMENT - COMANDOS PARA PRODUÇÃO

## Status Atual
✅ **Script testado com sucesso em desenvolvimento**
⚠️ **Pronto para deploy em produção**

## Comandos para Executar

### 1. Configurar Variáveis de Ambiente
```bash
# Configurar DATABASE_URL com suas credenciais Supabase
export DATABASE_URL="postgresql://postgres.[PROJECT_ID]:[SERVICE_ROLE_KEY]@db.[PROJECT_ID].supabase.co:5432/postgres"

# Configurar outras variáveis necessárias
export SUPABASE_URL="https://[PROJECT_ID].supabase.co"
export SUPABASE_ANON_KEY="[YOUR_ANON_KEY]"
export SUPABASE_SERVICE_ROLE_KEY="[YOUR_SERVICE_ROLE_KEY]"
```

### 2. Aplicar Migração RLS (Fase 1)
```bash
# Navegar para o Backend
cd /c/exclusivo/clinica-oncologica-v01/Backend

# Aplicar migração
psql $DATABASE_URL -f sql/migrations/002_incremental_rls_rollout.sql

# Verificar status
psql $DATABASE_URL -c "SELECT * FROM rls_rollout_status;"
```

### 3. Testar Localmente
```bash
# Instalar dependências Python se necessário
pip install -r requirements.txt

# Rodar testes RLS
python tests/test_rls_endpoints.py --url http://localhost:8000

# Ou usar o script de teste
bash scripts/run_rls_tests.sh http://localhost:8000
```

### 4. Deploy para Railway (Produção)
```bash
# Configurar Railway CLI
railway login
railway link

# Configurar variáveis de produção
railway variables set < .env.railway.production

# Deploy
railway up --environment=production

# Verificar logs
railway logs --environment=production
```

### 5. Monitoramento Contínuo
```bash
# Iniciar monitoramento (roda a cada 5 minutos)
bash scripts/monitor_rls.sh https://[YOUR_APP].railway.app 300

# Verificar health check
curl https://[YOUR_APP].railway.app/api/v1/health/rls/status

# Verificar alertas
curl https://[YOUR_APP].railway.app/api/v1/health/rls/alerts \
  -H "Authorization: Bearer [ADMIN_TOKEN]"
```

## Verificação de Sucesso

### ✅ Critérios para Fase 1 (48 horas)
- [ ] Migração aplicada com sucesso
- [ ] 7 tabelas com RLS habilitado
- [ ] Políticas read-only ativas
- [ ] Performance degradation < 10%
- [ ] Zero erros de permissão
- [ ] Monitoring dashboard funcionando

### 📊 Queries de Verificação
```sql
-- Verificar status RLS
SELECT * FROM rls_rollout_status;

-- Verificar políticas ativas
SELECT tablename, policyname, cmd
FROM pg_policies
WHERE schemaname = 'public';

-- Verificar performance
SELECT * FROM rls_performance_baseline;
```

## 🚨 Rollback de Emergência

Se algo der errado:

### Rollback Rápido (< 30 segundos)
```bash
# Via Railway
railway variables set SUPABASE_BYPASS_RLS=true
railway up

# Ou localmente
export SUPABASE_BYPASS_RLS=true
```

### Rollback Completo do Banco
```sql
-- Conectar ao banco
psql $DATABASE_URL

-- Desabilitar RLS
BEGIN;
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.patients DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.medical_reports DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.flow_states DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_responses DISABLE ROW LEVEL SECURITY;
COMMIT;
```

## 📈 Próximos Passos

### Após 48 horas de sucesso na Fase 1:
```bash
# Aplicar Fase 2 (políticas de escrita)
bash scripts/deploy_rls.sh production 2

# Ou manualmente
psql $DATABASE_URL -f sql/migrations/003_rls_phase2_write_policies.sql
```

## 📞 Suporte

Em caso de dúvidas ou problemas:
1. Verificar logs: `railway logs`
2. Checar monitoring: `bash scripts/monitor_rls.sh`
3. Consultar documentação: `docs/RLS_ROLLOUT_STRATEGY.md`

---

**Status**: Sistema pronto para deploy de produção
**Próxima ação**: Configurar DATABASE_URL e executar comandos acima
**Tempo estimado**: 10-15 minutos para deploy completo

---