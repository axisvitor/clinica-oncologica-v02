# Railway Deployment Checklist

**Projeto:** Clínica Oncológica - Hormonia Backend
**Última Atualização:** 2025-10-05

---

## 🚀 Checklist de Deploy Railway

### 📋 PRÉ-DEPLOY (Fazer ANTES de enviar para produção)

#### 1. Configuração de Arquivos

- [ ] `railway.toml` existe na raiz do projeto
- [ ] `backend-hormonia/Dockerfile` configurado com `$PORT`
- [ ] `backend-hormonia/Dockerfile.worker` existe (se usando Celery)
- [ ] `backend-hormonia/Dockerfile.beat` existe (se usando Celery)
- [ ] `frontend-hormonia/Dockerfile` existe
- [ ] `.github/workflows/railway-deploy.yml` configurado

#### 2. Variáveis de Ambiente (Railway Dashboard)

**OBRIGATÓRIAS - API BACKEND:**
- [ ] `DATABASE_URL` - PostgreSQL connection string
- [ ] `SECRET_KEY` - 64+ caracteres aleatórios
- [ ] `REDIS_URL` - Redis connection string (rediss:// com SSL)
- [ ] `ENVIRONMENT=production`
- [ ] `DEBUG=false`

**FIREBASE (obrigatório para auth):**
- [ ] `FIREBASE_PROJECT_ID`
- [ ] `FIREBASE_PRIVATE_KEY` (formato correto com `\n`)
- [ ] `FIREBASE_CLIENT_EMAIL`
- [ ] `FIREBASE_DATABASE_URL`

**SUPABASE (obrigatório para RLS):**
- [ ] `SUPABASE_URL`
- [ ] `SUPABASE_KEY` (service role key)

**REDIS (obrigatório para cache/sessions):**
- [ ] `REDIS_URL` (deve começar com `rediss://` para SSL)
- [ ] `REDIS_PASSWORD` (se aplicável)

**CELERY (se usando background tasks):**
- [ ] `CELERY_BROKER_URL` (geralmente = REDIS_URL)
- [ ] `CELERY_RESULT_BACKEND` (geralmente = REDIS_URL)

**OPCIONAL (mas recomendado):**
- [ ] `SENTRY_DSN` (para error tracking)
- [ ] `GEMINI_API_KEY` (se usando AI)
- [ ] `EVOLUTION_API_URL` (se usando WhatsApp)
- [ ] `EVOLUTION_API_KEY`

#### 3. Testes Locais

- [ ] `docker build` completa sem erros
- [ ] `docker run` inicia aplicação com sucesso
- [ ] Health check `/health` retorna 200 OK
- [ ] Database migrations aplicadas (`alembic upgrade head`)
- [ ] Tests passam (`pytest tests/`)
- [ ] Linting passa (`ruff check`)

#### 4. GitHub Actions

- [ ] Workflow `.github/workflows/railway-deploy.yml` configurado
- [ ] GitHub Secret `RAILWAY_TOKEN` configurado
- [ ] GitHub Secret `RAILWAY_BACKEND_URL` configurado (opcional)
- [ ] GitHub Secret `RAILWAY_FRONTEND_URL` configurado (opcional)
- [ ] Push para branch `main` ou `production` ativa workflow

---

## 🎯 DURANTE O DEPLOY

#### 1. Monitoramento do Deploy

- [ ] Abrir Railway Dashboard
- [ ] Abrir GitHub Actions tab
- [ ] Monitorar logs do Railway em tempo real
- [ ] Verificar status de cada serviço:
  - Backend API
  - Celery Worker
  - Celery Beat
  - Frontend

#### 2. Verificação de Build

- [ ] Build do backend completa (5-10 min esperado)
- [ ] Build do frontend completa (3-5 min esperado)
- [ ] Sem erros críticos nos logs de build
- [ ] Docker images criadas com sucesso

#### 3. Verificação de Startup

- [ ] Backend API inicia sem erros
- [ ] Health check `/health` começa a retornar 200
- [ ] Database conectada (verificar logs)
- [ ] Redis conectado (verificar logs)
- [ ] Migrations aplicadas automaticamente (se configurado)

---

## ✅ PÓS-DEPLOY (Fazer APÓS deploy completar)

#### 1. Validação de Serviços

**Backend API:**
- [ ] URL pública acessível
- [ ] `GET /health` retorna 200 OK
- [ ] `GET /health/readiness` retorna 200 OK
- [ ] `GET /health/liveness` retorna 200 OK
- [ ] `GET /docs` (Swagger) acessível
- [ ] `GET /test` retorna mensagem correta

**Frontend:**
- [ ] URL pública acessível
- [ ] Página carrega sem erros 404
- [ ] Assets estáticos (CSS/JS) carregam
- [ ] Chamadas API funcionam (verificar Network tab)

**Celery (se aplicável):**
- [ ] Workers aparecem no Railway dashboard
- [ ] Logs mostram workers processando tasks
- [ ] Beat scheduler executando tarefas agendadas

#### 2. Testes Funcionais

**Autenticação:**
- [ ] Login funciona
- [ ] Registro de usuário funciona
- [ ] Token JWT válido retornado
- [ ] Logout funciona

**Database:**
- [ ] Queries executam com sucesso
- [ ] RLS (Row Level Security) funcionando
- [ ] Migrations aplicadas corretamente

**Cache/Redis:**
- [ ] Cache funcionando (testar endpoint com cache)
- [ ] Sessions persistindo entre requests
- [ ] Rate limiting ativo (se configurado)

**APIs Externas:**
- [ ] Firebase Auth funcionando
- [ ] Supabase conexão OK
- [ ] Gemini AI respondendo (se aplicável)
- [ ] WhatsApp integration OK (se aplicável)

#### 3. Performance e Monitoramento

**Métricas Iniciais:**
- [ ] Response time < 500ms (média)
- [ ] Memory usage estável
- [ ] CPU usage < 70%
- [ ] No memory leaks (monitorar 24h)

**Logs:**
- [ ] Sem erros críticos (ERROR/CRITICAL)
- [ ] Warnings investigados
- [ ] Structured logging funcionando
- [ ] Log aggregation ativo (se configurado)

**Health Checks:**
- [ ] Railway health checks passando
- [ ] Nenhum restart inesperado
- [ ] Uptime > 99% após 24h

#### 4. Segurança

- [ ] HTTPS habilitado (Railway faz automaticamente)
- [ ] CORS configurado corretamente
- [ ] Rate limiting ativo
- [ ] Secrets não expostos em logs
- [ ] Database credentials seguras

#### 5. Rollback Plan

- [ ] Versão anterior identificada
- [ ] Comando de rollback testado
- [ ] Tempo de rollback estimado
- [ ] Stakeholders notificados do deploy

---

## 🚨 TROUBLESHOOTING

### Backend não inicia

1. **Verificar logs Railway:**
   ```bash
   railway logs --service backend-api
   ```

2. **Verificar variáveis de ambiente:**
   ```bash
   railway variables
   ```

3. **Verificar health check:**
   ```bash
   curl https://your-backend.railway.app/health
   ```

4. **Verificar database:**
   - Database URL correto?
   - Database acessível do Railway?
   - Migrations aplicadas?

### Health Check falhando

1. **Verificar timeout:**
   - Health check demora > 10s?
   - Aumentar timeout no `railway.toml`

2. **Verificar dependências:**
   - Database acessível?
   - Redis acessível?
   - ServiceProvider inicializa?

3. **Verificar endpoint:**
   - `/health` retorna 200?
   - JSON válido?
   - Sem exceções?

### Celery Worker não processa tasks

1. **Verificar REDIS_URL:**
   - Deve ser `rediss://` (com SSL)
   - Password correto?
   - Acessível do Railway?

2. **Verificar logs:**
   ```bash
   railway logs --service celery-worker
   ```

3. **Verificar queues:**
   - Tasks sendo enviadas?
   - Worker conectado ao broker?

### Frontend não carrega

1. **Verificar build:**
   - `npm run build` completou?
   - Sem erros de TypeScript?

2. **Verificar environment variables:**
   - `VITE_API_URL` correto?
   - Aponta para Railway backend URL?

3. **Verificar CORS:**
   - Backend permite origem do frontend?
   - Headers CORS corretos?

---

## 📊 Métricas de Sucesso

### Critérios de Aceitação

- [ ] Uptime > 99.5% nas primeiras 24h
- [ ] Response time médio < 500ms
- [ ] Zero erros críticos em produção
- [ ] Todos os health checks passando
- [ ] Nenhum restart inesperado
- [ ] Memory usage < 80% alocado
- [ ] CPU usage < 70% alocado

### KPIs a Monitorar (7 dias)

- Uptime %
- Average Response Time
- Error Rate %
- Request Volume
- Database Query Time
- Cache Hit Rate
- Celery Task Success Rate

---

## 🔄 Processo de Rollback

### Quando fazer rollback:

- Erros críticos em produção (>5% requests)
- Health checks falhando consistentemente
- Performance degradada (>2x slower)
- Data corruption detectada
- Security vulnerability descoberta

### Como fazer rollback:

1. **Via Railway Dashboard:**
   - Ir para "Deployments"
   - Selecionar deployment anterior
   - Clicar "Redeploy"

2. **Via Railway CLI:**
   ```bash
   railway rollback
   ```

3. **Via Git:**
   ```bash
   git revert HEAD
   git push origin main
   ```

---

## 📞 Contatos de Emergência

- **DevOps Lead:** [Nome/Email]
- **Backend Lead:** [Nome/Email]
- **Railway Support:** https://railway.app/support
- **Status Page:** https://status.railway.app

---

## 📝 Histórico de Deploys

| Data | Versão | Deploy Por | Status | Notas |
|------|--------|------------|--------|-------|
| 2025-10-05 | v2.0.0 | [Nome] | ✅ | Initial Railway deploy |
| | | | | |

---

**Última Revisão:** 2025-10-05
**Próxima Revisão:** Após primeiro deploy em produção
