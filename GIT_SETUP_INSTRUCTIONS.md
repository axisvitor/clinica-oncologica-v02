# 🚀 Instruções de Setup Git e Push

**Status Atual**:
- ✅ Repositório Git inicializado
- ✅ Remote configurado: https://github.com/axisvitor/clinica-oncologica-v02.git
- ✅ Branch `docs-refactor-py313` criada
- ✅ Todos os arquivos prontos para commit

---

## 📋 Passos para Commit e Push

### 1. Abrir Terminal na Pasta do Projeto

```bash
cd "c:\Meu Projetos\clinica-oncologica-v02"
```

### 2. Verificar Status

```bash
git status
```

**Esperado**: Muitos arquivos "Untracked" prontos para serem adicionados.

### 3. Adicionar Todos os Arquivos

```bash
git add .
```

### 4. Fazer o Commit

```bash
git commit -m "docs: complete documentation refactor + Python 3.13 upgrade

- Reorganize docs by domain (api, security, db, deployment, redis, etc)
- Move 15 canonical docs to proper locations
- Archive 13 incident reports to docs/incidents/_archive/
- Delete 4 duplicate/obsolete files
- Create navigable README indices for all projects
- Add CI/CD for docs quality (markdownlint, lychee, cspell)
- Upgrade all configs and docs to Python 3.13
- Update Dockerfiles to python:3.13-slim
- Update CI workflows to Python 3.13
- Add comprehensive Python 3.13 upgrade guide
- Fix internal links to moved files

Files modified: 54
Files created: 11
Files moved: 15
Files archived: 13
Files deleted: 4

🤖 Generated with Claude Code
https://claude.com/claude-code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 5. Fazer o Push

```bash
git push -u origin docs-refactor-py313
```

**Nota**: Se pedir autenticação, use suas credenciais do GitHub.

---

## 🔐 Se Usar Autenticação via Token

Se o GitHub pedir senha, use um **Personal Access Token** (não senha):

1. Acesse: https://github.com/settings/tokens
2. Gerar novo token (classic)
3. Permissões: `repo` (full control)
4. Copie o token
5. Cole quando pedir senha

---

## 📝 Após o Push

### 1. Abrir Pull Request

1. Acesse: https://github.com/axisvitor/clinica-oncologica-v02
2. Você verá um banner "Compare & pull request" - clique
3. Título: `docs: complete documentation refactor + Python 3.13 upgrade`
4. Descrição: Cole o conteúdo de [REFACTOR_COMPLETE.md](REFACTOR_COMPLETE.md)
5. Criar Pull Request

### 2. Verificar CI/CD

Os seguintes workflows devem rodar automaticamente:

#### ✅ docs-quality.yml
- Markdown lint
- Link checker
- Structure validation
- Spell check

**Se houver warnings**:
- Spelling: adicionar palavras em `.cspell.json`
- Links: corrigir URLs quebradas
- Lint: ajustar formatação

#### ✅ rls-api-tests.yml
- Setup Python 3.13
- Instalar dependências
- Iniciar FastAPI
- Rodar testes RLS via API

**Secrets necessários no GitHub** (Settings → Secrets → Actions):
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `FIREBASE_ADMIN_PROJECT_ID`
- `FIREBASE_ADMIN_PRIVATE_KEY`
- `FIREBASE_ADMIN_CLIENT_EMAIL`
- `SECRET_KEY`

### 3. Merge após CI Verde

Quando todos os checks passarem:
1. Fazer merge do PR
2. Deletar branch remota (opcional)
3. Atualizar branch local:
```bash
git checkout main
git pull origin main
git branch -d docs-refactor-py313
```

---

## 🚢 Deploy em Staging

Após merge na `main`:

### Railway / Render / Vercel
1. Configurar variáveis de ambiente
2. Deploy automático ou manual
3. Verificar logs:
   - Python version: `3.13.x`
   - Dependencies instaladas
   - Servidor rodando

### Validação
```bash
# Health check
curl https://seu-backend.railway.app/health

# Test endpoint
curl https://seu-backend.railway.app/api/v1/patients
```

---

## 🐛 Troubleshooting

### Erro: "failed to push"
```bash
git pull origin docs-refactor-py313 --rebase
git push -u origin docs-refactor-py313
```

### Erro: "authentication failed"
- Use Personal Access Token
- Ou configure SSH keys

### Erro: "CI failing"
- Ver logs no GitHub Actions
- Corrigir localmente
- Commit e push novamente

### Python 3.13 não encontrado
- Verificar Dockerfile: `FROM python:3.13-slim`
- Verificar workflow: `python-version: '3.13'`

---

## 📚 Referências

- **Resumo Completo**: [REFACTOR_COMPLETE.md](REFACTOR_COMPLETE.md)
- **Plano Detalhado**: [DOCS_REFACTOR_PLAN.md](DOCS_REFACTOR_PLAN.md)
- **Python 3.13**: [backend-hormonia/docs/PYTHON_313_UPGRADE.md](backend-hormonia/docs/PYTHON_313_UPGRADE.md)
- **Próximos Passos**: [DOCS_NEXT_STEPS.md](DOCS_NEXT_STEPS.md)

---

## ✅ Checklist Final

Antes de fazer deploy em produção:

- [ ] PR criado e revisado
- [ ] CI passou (docs-quality + rls-api-tests)
- [ ] Deploy em staging OK
- [ ] Python 3.13 validado
- [ ] Testes manuais passaram
- [ ] Performance monitorada
- [ ] Rollback plan definido
- [ ] Merge para main
- [ ] Deploy em produção
- [ ] Monitorar por 24-48h

---

**Executado por**: Claude Code
**Data**: 2025-10-02
**Status**: ✅ Pronto para Push
