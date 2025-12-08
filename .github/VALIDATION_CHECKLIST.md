# ✅ CI/CD Pipeline Validation Checklist

## Pre-Deployment Validation

### 1. Verificar Estrutura de Arquivos

```bash
# Verificar se todos os workflows foram criados
ls -la .github/workflows/ | grep -E "(ci|cd-staging|cd-production|security|pr-checks|release).yml"

# Verificar configurações
ls -la .github/ | grep -E "(dependabot.yml|CODEOWNERS|changelog-config.json)"

# Verificar documentação
ls -la docs/ | grep -E "CI_CD"
```

**Esperado**: 6 workflows + 3 configs + 2 docs

### 2. Validar Sintaxe YAML

```bash
# Instalar yamllint (se necessário)
pip install yamllint

# Validar todos os workflows
yamllint .github/workflows/*.yml

# Validar dependabot
yamllint .github/dependabot.yml
```

**Esperado**: 0 erros de sintaxe

### 3. Validar GitHub Actions Localmente

```bash
# Instalar act (https://github.com/nektos/act)
# macOS
brew install act

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Windows
choco install act-cli

# Listar workflows
act -l

# Dry-run do CI
act pull_request -n

# Testar job específico (sem executar)
act -j lint-backend -n
```

**Esperado**: Workflows listados sem erros

### 4. Verificar Secrets Necessários

```bash
# Via GitHub CLI
gh secret list

# Verificar se todos estão configurados
REQUIRED_SECRETS=(
  "RAILWAY_TOKEN_STAGING"
  "RAILWAY_TOKEN_PRODUCTION"
  "VERCEL_TOKEN"
  "VERCEL_ORG_ID"
  "VERCEL_PROJECT_ID"
)

for secret in "${REQUIRED_SECRETS[@]}"; do
  if gh secret list | grep -q "$secret"; then
    echo "✅ $secret configurado"
  else
    echo "❌ $secret FALTANDO"
  fi
done
```

**Esperado**: Todos os secrets obrigatórios configurados

### 5. Verificar Environments

```bash
# Via GitHub CLI
gh api repos/:owner/:repo/environments | jq '.environments[].name'

# Verificar se existem
REQUIRED_ENVS=(
  "production-approval"
  "production-backend"
  "production-frontend"
  "staging-backend"
  "staging-frontend"
)
```

**Esperado**: 5 environments configurados

### 6. Validar Branch Protection

```bash
# Verificar proteção da main
gh api repos/:owner/:repo/branches/main/protection | jq '.required_status_checks.contexts'

# Verificar proteção da develop
gh api repos/:owner/:repo/branches/develop/protection | jq '.required_status_checks.contexts'
```

**Esperado**: Status checks configurados

### 7. Testar Linting Localmente

```bash
# Backend
cd backend-hormonia
ruff check .
mypy app --ignore-missing-imports
isort . --check-only

# Frontend
cd frontend-hormonia
npm run lint
npm run typecheck:ci
```

**Esperado**: 0 erros

### 8. Testar Tests Localmente

```bash
# Backend (requer PostgreSQL e Redis rodando)
cd backend-hormonia
pytest tests/ -v

# Frontend
cd frontend-hormonia
npm run test:ci
```

**Esperado**: Todos os testes passando

### 9. Testar Docker Build

```bash
# Backend
cd backend-hormonia
docker build -t hormonia-backend:test .

# Frontend
cd frontend-hormonia
npm run build
docker build -t hormonia-frontend:test .
```

**Esperado**: Builds bem-sucedidos

### 10. Validar Security Scans

```bash
# Python - Bandit
cd backend-hormonia
pip install bandit[toml]
bandit -r app/ -ll

# Python - Safety
pip install safety
safety check --file requirements.txt

# JavaScript - npm audit
cd frontend-hormonia
npm audit --audit-level=moderate

# Secrets - Gitleaks (local)
docker run -v $(pwd):/path zricethezav/gitleaks:latest detect --source="/path" -v
```

**Esperado**: Sem vulnerabilidades críticas

## Post-Configuration Validation

### 11. Criar PR de Teste

```bash
# Criar branch de teste
git checkout -b test/ci-pipeline-validation

# Fazer pequena mudança
echo "# CI/CD Pipeline Test" >> TEST.md

# Commit e push
git add TEST.md
git commit -m "test: validate CI/CD pipeline"
git push origin test/ci-pipeline-validation

# Criar PR
gh pr create \
  --title "test: validate CI/CD pipeline" \
  --body "Testing CI/CD workflows" \
  --base develop
```

**Verificar**:
- ✅ PR checks iniciam automaticamente
- ✅ Lint jobs executam
- ✅ Test jobs executam
- ✅ Security scan executa
- ✅ Labels adicionados automaticamente
- ✅ Reviewers atribuídos

### 12. Monitorar Workflow Execution

```bash
# Ver runs em andamento
gh run list --workflow=ci.yml

# Ver logs de um run
gh run view <run-id> --log

# Ver status de um run
gh run view <run-id>

# Re-run em caso de falha
gh run rerun <run-id>
```

### 13. Validar Artifacts

```bash
# Listar artifacts de um run
gh run view <run-id> --json artifacts

# Download de artifacts
gh run download <run-id>

# Verificar conteúdo
ls -la
```

**Esperado**: Coverage reports, test results, security reports

### 14. Testar Staging Deployment

```bash
# Push para develop (após merge do PR de teste)
git checkout develop
git pull origin develop

# Monitorar deployment
gh run list --workflow=cd-staging.yml

# Verificar logs
gh run view <run-id> --log
```

**Verificar**:
- ✅ Docker images built
- ✅ Railway deployment sucesso
- ✅ Vercel deployment sucesso
- ✅ E2E tests passaram
- ✅ Smoke tests passaram
- ✅ Notificação Slack enviada

### 15. Validar Health Checks

```bash
# Backend staging
curl -f https://staging-api.hormonia.com/api/health

# Frontend staging
curl -f https://staging.hormonia.com

# Detailed health
curl https://staging-api.hormonia.com/api/v2/health | jq
```

**Esperado**: Status 200, healthy: true

### 16. Testar Release Process

```bash
# Criar tag de release
git checkout main
git pull origin main
git tag v1.0.0-test
git push origin v1.0.0-test

# Monitorar release workflow
gh run list --workflow=release.yml

# Verificar release criado
gh release view v1.0.0-test
```

**Verificar**:
- ✅ Release criado no GitHub
- ✅ Changelog gerado
- ✅ Artifacts anexados
- ✅ Docker images publicados
- ✅ Deployment issue criado

### 17. Validar Production Deployment

```bash
# Monitorar production deployment
gh run list --workflow=cd-production.yml

# Verificar logs
gh run view <run-id> --log
```

**Verificar**:
- ✅ Approval solicitado
- ✅ Pre-deployment checks passaram
- ✅ Production deployment aguardando
- ⚠️ NÃO aprovar no teste inicial

### 18. Verificar Security Alerts

```bash
# Via GitHub UI
# Settings → Security → Code scanning alerts
# Settings → Security → Dependabot alerts

# Via CLI
gh api repos/:owner/:repo/code-scanning/alerts | jq '.[].number'
```

**Esperado**: Alerts configurados, nenhum critical aberto

### 19. Validar Dependabot

```bash
# Verificar PRs do Dependabot
gh pr list --author app/dependabot

# Verificar configuração
cat .github/dependabot.yml
```

**Esperado**: Dependabot ativo, PRs podem existir

### 20. Cleanup do Teste

```bash
# Deletar tag de teste
git tag -d v1.0.0-test
git push origin :refs/tags/v1.0.0-test

# Fechar PR de teste
gh pr close test/ci-pipeline-validation

# Deletar branch de teste
git branch -D test/ci-pipeline-validation
git push origin --delete test/ci-pipeline-validation
```

## Continuous Monitoring

### Daily Checks

```bash
# Verificar failed workflows nas últimas 24h
gh run list --status failure --created ">$(date -d '1 day ago' +%Y-%m-%d)"

# Verificar security alerts novos
gh api repos/:owner/:repo/code-scanning/alerts | jq '[.[] | select(.created_at > (now - 86400 | todate))]'
```

### Weekly Checks

```bash
# Verificar dependency updates pendentes
gh pr list --label dependencies

# Review security scan results
gh run list --workflow=security.yml --limit 1

# Check deployment success rate
gh run list --workflow=cd-staging.yml --limit 10 | grep -c success
```

### Monthly Checks

```bash
# Audit secrets (verificar expiração)
# Audit team members
# Review workflow performance metrics
# Update documentation se necessário
```

## Troubleshooting Commands

### Workflow Debugging

```bash
# Habilitar debug logs
gh secret set ACTIONS_STEP_DEBUG --body "true"
gh secret set ACTIONS_RUNNER_DEBUG --body "true"

# Re-run com debug
gh run rerun <run-id>

# Desabilitar após debug
gh secret delete ACTIONS_STEP_DEBUG
gh secret delete ACTIONS_RUNNER_DEBUG
```

### Cache Management

```bash
# Listar caches
gh api repos/:owner/:repo/actions/caches | jq '.actions_caches[].key'

# Deletar cache específico
gh api repos/:owner/:repo/actions/caches/:cache-id -X DELETE

# Limpar todos os caches (força rebuild)
gh api repos/:owner/:repo/actions/caches --paginate | jq -r '.actions_caches[].id' | xargs -I {} gh api repos/:owner/:repo/actions/caches/{} -X DELETE
```

### Workflow Cancellation

```bash
# Cancelar runs em andamento
gh run list --status in_progress --json databaseId -q '.[].databaseId' | xargs -I {} gh run cancel {}
```

## Success Criteria

Pipeline está pronto para produção quando:

- ✅ Todos os 6 workflows criados e validados
- ✅ Syntax validation passou (yamllint)
- ✅ Todos os secrets obrigatórios configurados
- ✅ 5 environments configurados
- ✅ Branch protection habilitada em main e develop
- ✅ PR de teste passou em todos os checks
- ✅ Staging deployment funcionando
- ✅ Health checks automáticos passando
- ✅ Security scans executando sem erros críticos
- ✅ Dependabot ativo
- ✅ Notificações Slack funcionando
- ✅ Release process testado
- ✅ Documentação completa e atualizada

---

**Status Check**: `./validate-cicd.sh` (criar script baseado neste checklist)
