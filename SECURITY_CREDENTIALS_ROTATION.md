# 🔐 Rotação de Credenciais Expostas - URGENTE

## ⚠️ Problema Identificado

Credenciais sensíveis foram encontradas versionadas no repositório:

### Backend (`.env` na raiz)
- **FLOW_NEXUS_SESSION**: Token JWT completo com `access_token`, `refresh_token` e dados do usuário
- **Risco**: Acesso não autorizado ao Supabase Flow Nexus

### Frontend (`frontend-hormonia/.env`)
- Firebase API keys
- Supabase anon keys
- URLs de produção

### Quiz (`quiz-mensal-interface/.env`)
- Tokens de acesso
- Credenciais de API

## 🚨 Ações Imediatas Necessárias

### 1. Revogar Credenciais Expostas

#### Supabase/Flow Nexus
```bash
# Acessar Supabase Dashboard
# 1. Ir para Settings > API
# 2. Regenerar Service Role Key
# 3. Atualizar FLOW_NEXUS_SESSION com nova sessão
```

#### Firebase
```bash
# Acessar Firebase Console
# 1. Project Settings > Service Accounts
# 2. Generate new private key
# 3. Atualizar configuração do frontend
```

### 2. Mover Credenciais para Arquivos Locais

#### Backend
```bash
cd backend-hormonia
# Criar .env.local com credenciais reais
cp .env .env.local

# Limpar .env (manter apenas exemplos)
echo "# See .env.example for configuration template" > .env
echo "# Copy .env.example to .env.local and fill with real values" >> .env
```

#### Frontend
```bash
cd frontend-hormonia
# Criar .env.local
cp .env .env.local

# Limpar .env
echo "# See .env.example for configuration" > .env
```

#### Quiz
```bash
cd quiz-mensal-interface
# Criar .env.local
cp .env .env.local

# Limpar .env
echo "# See .env.example for configuration" > .env
```

### 3. Atualizar .gitignore

Adicionar ao `.gitignore` na raiz:
```gitignore
# Environment files with real credentials
.env.local
.env.*.local
*.env.local

# Keep only .env.example files
!.env.example
!**/.env.example
```

### 4. Remover Credenciais do Histórico Git

```bash
# CUIDADO: Isso reescreve o histórico
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env frontend-hormonia/.env quiz-mensal-interface/.env" \
  --prune-empty --tag-name-filter cat -- --all

# Forçar push (coordenar com equipe)
git push origin --force --all
git push origin --force --tags
```

**Alternativa mais segura**: Usar BFG Repo-Cleaner
```bash
# Instalar BFG
# https://rtyley.github.io/bfg-repo-cleaner/

# Remover arquivos sensíveis
bfg --delete-files .env
bfg --delete-files '*.env'

# Limpar histórico
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

## 📋 Checklist de Segurança

- [ ] Revogar FLOW_NEXUS_SESSION token no Supabase
- [ ] Regenerar Firebase API keys
- [ ] Regenerar Supabase anon keys
- [ ] Criar `.env.local` em todos os módulos
- [ ] Limpar arquivos `.env` versionados
- [ ] Atualizar `.gitignore`
- [ ] Remover credenciais do histórico Git
- [ ] Notificar equipe sobre novas credenciais
- [ ] Atualizar pipelines CI/CD com novas secrets
- [ ] Atualizar Railway/Netlify environment variables
- [ ] Documentar processo de rotação de credenciais

## 🔄 Processo de Rotação Regular

### Frequência Recomendada
- **Produção**: A cada 90 dias
- **Staging**: A cada 180 dias
- **Desenvolvimento**: Anualmente ou quando comprometido

### Automação
```bash
# Script de rotação (exemplo)
#!/bin/bash
# rotate-credentials.sh

echo "🔄 Iniciando rotação de credenciais..."

# 1. Backup credenciais atuais
cp .env.local .env.local.backup.$(date +%Y%m%d)

# 2. Gerar novas credenciais
# (implementar lógica específica para cada serviço)

# 3. Testar novas credenciais
make test-integration

# 4. Atualizar produção
# (via Railway CLI ou Netlify CLI)

echo "✅ Rotação concluída"
```

## 📚 Referências

- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [GitHub: Removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/)

## 🆘 Suporte

Em caso de dúvidas ou incidentes de segurança:
1. Revogar credenciais imediatamente
2. Notificar tech lead
3. Documentar incidente
4. Implementar correções
5. Revisar processos de segurança
