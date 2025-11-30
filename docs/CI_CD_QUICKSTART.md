# CI/CD Quick Start Guide

## 🚀 Setup em 5 Minutos

### 1. Configurar Secrets no GitHub

Acesse: `Settings → Secrets and variables → Actions → New repository secret`

```bash
# Obrigatórios para Staging
RAILWAY_TOKEN_STAGING=<railway_token_staging>
VERCEL_TOKEN=<vercel_token>
VERCEL_ORG_ID=<vercel_org_id>
VERCEL_PROJECT_ID=<vercel_project_id>

# Obrigatórios para Production
RAILWAY_TOKEN_PRODUCTION=<railway_token_production>

# Opcionais (mas recomendados)
CODECOV_TOKEN=<codecov_token>
SNYK_TOKEN=<snyk_token>
SLACK_WEBHOOK_URL=<slack_webhook>
SLACK_WEBHOOK_SECURITY=<slack_security_webhook>
SLACK_WEBHOOK_CRITICAL=<slack_critical_webhook>
```

### 2. Configurar Ambientes no GitHub

Acesse: `Settings → Environments`

**Criar 4 ambientes:**

1. **production-approval**
   - Required reviewers: Adicionar DevOps team
   - Deployment branches: Apenas tags

2. **production-backend**
   - Required reviewers: Nenhum
   - URL: https://api.hormonia.com

3. **production-frontend**
   - Required reviewers: Nenhum
   - URL: https://hormonia.com

4. **staging-backend**
   - Required reviewers: Nenhum
   - URL: https://staging-api.hormonia.com

5. **staging-frontend**
   - Required reviewers: Nenhum
   - URL: https://staging.hormonia.com

### 3. Configurar Branch Protection

Acesse: `Settings → Branches → Add rule`

**Para branch `main`:**
```yaml
Branch name pattern: main
☑ Require pull request reviews (1 approver)
☑ Require status checks to pass
  Status checks:
    - ci-status
    - lint-backend
    - lint-frontend
    - test-backend
    - test-frontend
☑ Require branches to be up to date
☑ Do not allow bypassing (remover admin)
☑ Restrict pushes to specific people/teams
☐ Allow force pushes: OFF
☐ Allow deletions: OFF
```

**Para branch `develop`:**
```yaml
Branch name pattern: develop
☑ Require pull request reviews (1 approver)
☑ Require status checks to pass
☑ Require branches to be up to date
```

### 4. Configurar Teams (opcional mas recomendado)

Acesse: `Settings → Collaborators and teams`

Criar e adicionar times:
- `@devops-team` - DevOps engineers
- `@backend-team` - Backend developers
- `@frontend-team` - Frontend developers
- `@security-team` - Security specialists
- `@dba-team` - Database administrators

## 📋 Workflows Disponíveis

| Workflow | Trigger | Descrição |
|----------|---------|-----------|
| **CI** | Push/PR para main, develop | Lint, test, build |
| **CD Staging** | Push para develop | Deploy automático staging |
| **CD Production** | Release tag (v1.0.0) | Deploy production com aprovação |
| **Security** | Weekly + Push/PR | Scans de segurança |
| **PR Checks** | Pull request | Validações automáticas |
| **Release** | Tag vX.X.X | Criar release GitHub |

## 🎯 Fluxo de Trabalho Recomendado

### Feature Development
```bash
# 1. Criar feature branch
git checkout -b feature/new-feature

# 2. Desenvolver e commitar
git commit -m "feat: add new feature"

# 3. Push e criar PR
git push origin feature/new-feature

# 4. CI roda automaticamente
# - Linting
# - Tests
# - Security scan

# 5. Aprovação e merge para develop
# → Staging deployment automático

# 6. Testes em staging
# → E2E tests rodam automaticamente

# 7. Merge develop → main
# 8. Criar release tag
git tag v1.0.0
git push origin v1.0.0

# 9. Production deployment
# → Requer aprovação manual
# → Smoke tests automáticos
# → Monitoring 15 min
```

### Hotfix Production
```bash
# 1. Branch direto da main
git checkout main
git checkout -b hotfix/critical-fix

# 2. Fix e commit
git commit -m "fix: critical security issue"

# 3. PR para main
git push origin hotfix/critical-fix

# 4. Após aprovação e merge
git tag v1.0.1
git push origin v1.0.1

# 5. Deployment automático
# → Aprovação rápida necessária
```

## 🔧 Comandos Úteis

### Testar Workflows Localmente

```bash
# Instalar act (GitHub Actions localmente)
brew install act  # macOS
# ou
choco install act  # Windows

# Rodar workflow CI
act -j ci-status

# Rodar job específico
act -j lint-backend
```

### Verificar Status

```bash
# Ver workflows rodando
gh workflow list

# Ver runs de um workflow
gh run list --workflow=ci.yml

# Ver logs de um run
gh run view <run-id> --log
```

### Disparar Workflow Manualmente

```bash
# Via GitHub CLI
gh workflow run ci.yml

# Staging deployment
gh workflow run cd-staging.yml

# Com inputs
gh workflow run cd-production.yml -f skip_approval=true
```

## 🚨 Troubleshooting Rápido

### Pipeline falha no CI

```bash
# 1. Ver logs
gh run view --log

# 2. Rodar testes localmente
cd backend-hormonia && pytest
cd frontend-hormonia && npm test

# 3. Re-run failed jobs
gh run rerun <run-id> --failed
```

### Deploy staging falha

```bash
# 1. Verificar secrets
gh secret list

# 2. Verificar Railway logs
railway logs --service backend-staging

# 3. Verificar Vercel deployment
vercel logs <deployment-url>
```

### Security scan bloqueia PR

```bash
# 1. Ver relatório completo
gh run view <run-id>

# 2. Baixar artifacts
gh run download <run-id>

# 3. Fix vulnerabilities
# Python: safety check --file requirements.txt
# npm: npm audit fix
```

## 📊 Monitoramento

### Acessar Dashboards

- **GitHub Actions**: `Actions` tab no repositório
- **Codecov**: https://codecov.io/gh/<org>/<repo>
- **Security**: `Security` → `Code scanning alerts`
- **Dependabot**: `Security` → `Dependabot alerts`

### Métricas Importantes

- ✅ CI success rate: > 95%
- ⏱️ CI duration: < 15 min
- 🎯 Test coverage: > 80%
- 🚀 Deployment frequency: Daily (staging)
- ⚡ Mean time to recovery: < 1 hour

## 🔒 Security Checklist

Antes do primeiro deployment:

- [ ] Todos os secrets configurados
- [ ] Branch protection habilitada
- [ ] CODEOWNERS configurado
- [ ] Ambientes de deployment criados
- [ ] Dependabot ativado
- [ ] Security scanning funcionando
- [ ] Slack notifications testadas
- [ ] Rollback plan documentado

## 📚 Próximos Passos

1. ✅ Testar CI com PR de teste
2. ✅ Fazer deploy em staging
3. ✅ Rodar E2E tests em staging
4. ✅ Criar primeiro release
5. ✅ Deploy em production
6. ✅ Configurar monitoring adicional
7. ✅ Treinar equipe nos workflows

## 🆘 Suporte

- 📖 Documentação completa: `docs/CI_CD_SETUP.md`
- 💬 Slack: #devops-support
- 🐛 Issues: Usar label `ci/cd`
- 📧 Email: devops@hormonia.com
