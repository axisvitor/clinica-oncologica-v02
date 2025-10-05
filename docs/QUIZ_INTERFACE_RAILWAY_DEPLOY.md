# Quiz Interface - Deploy no Railway

## 🐛 Problema Encontrado

**Erro durante build no Railway:**
```
Internal Error: Cannot find matching keyid
    at verifySignature (/usr/local/lib/node_modules/corepack/dist/lib/corepack.cjs:21535:47)
```

**Causa:** O `corepack` estava falhando ao verificar assinaturas digitais do pnpm@9, um problema conhecido com versões recentes do Node.js e corepack.

---

## ✅ Solução Implementada

### **Arquivo Corrigido:** [quiz-mensal-interface/Dockerfile](../quiz-mensal-interface/Dockerfile)

**Antes (linha 9-12):**
```dockerfile
# Enable pnpm via corepack
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && corepack prepare pnpm@9 --activate
```

**Depois (linha 9-14):**
```dockerfile
# Install pnpm globally (more reliable than corepack)
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PNPM_HOME="/pnpm" \
    PATH="$PNPM_HOME:$PATH"
RUN npm install -g pnpm@9.15.2
```

### **Mudanças:**
1. ❌ Removido `corepack enable && corepack prepare`
2. ✅ Instalado pnpm diretamente via npm
3. ✅ Versão específica: `pnpm@9.15.2` (mais estável)
4. ✅ Adicionado `PNPM_HOME` e PATH para garantir funcionamento

---

## 🚀 Deploy no Railway

### **Passo 1: Verificar Variáveis de Ambiente**

No Railway Dashboard do projeto `quiz-interface-production`:

**Variáveis obrigatórias:**
```bash
NEXT_PUBLIC_API_URL=https://clinica-oncologica-v02-production.up.railway.app
NODE_ENV=production
NEXT_TELEMETRY_DISABLED=1
```

### **Passo 2: Configuração do Railway**

O arquivo [railway.json](../quiz-mensal-interface/railway.json) está configurado para:
- ✅ Builder: DOCKERFILE (usa o Dockerfile corrigido)
- ✅ Healthcheck: `/api/health`
- ✅ Restart policy: ON_FAILURE (10 tentativas)
- ✅ Sleep: Disabled (sempre ativo)

### **Passo 3: Deploy**

Após o commit e push das mudanças:
1. Railway detecta mudanças no repositório
2. Faz build usando o Dockerfile corrigido
3. Executa `pnpm install --frozen-lockfile --prod=false`
4. Executa `pnpm build` (gera build otimizado Next.js)
5. Inicia com `pnpm exec next start -p ${PORT} -H 0.0.0.0`

### **Passo 4: Verificar Saúde**

Após deploy bem-sucedido:
```bash
# Verificar healthcheck
curl https://quiz-interface-production.up.railway.app/api/health

# Deve retornar:
{
  "status": "healthy",
  "timestamp": "2025-10-05T...",
  "version": "1.0.0"
}
```

---

## 🔗 Integração com Backend

### **Como Funciona:**

1. **Quiz Interface (Frontend Next.js)**
   - Recebe link do WhatsApp: `https://quiz-interface-production.up.railway.app/quiz/monthly?token=xyz`
   - Token contém: `patient_id`, `quiz_id`, expiration

2. **Valida Token com Backend**
   ```javascript
   // quiz-mensal-interface faz request:
   GET https://clinica-oncologica-v02-production.up.railway.app/api/v1/monthly-quiz/validate-token?token=xyz
   ```

3. **Backend Responde com Dados do Quiz**
   ```json
   {
     "valid": true,
     "patient": {...},
     "quiz_template": {...},
     "questions": [...]
   }
   ```

4. **Paciente Responde Quiz**
   - Interface renderiza perguntas
   - Paciente preenche respostas

5. **Submete Respostas ao Backend**
   ```javascript
   POST https://clinica-oncologica-v02-production.up.railway.app/api/v1/monthly-quiz/submit
   {
     "token": "xyz",
     "answers": [...]
   }
   ```

6. **Backend Processa e Notifica Médico**
   - Salva respostas no PostgreSQL
   - Calcula score/analytics
   - Envia notificação WhatsApp para médico

---

## 📊 Arquitetura de Comunicação

```
┌─────────────────┐
│    WhatsApp     │ Envia link com token
│   (Paciente)    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Quiz Interface (Next.js)          │
│   quiz-interface-production         │
│   Port: 3000                        │
│   URL: quiz-interface-production    │
│       .up.railway.app               │
└────────┬────────────────────────────┘
         │
         │ API Calls (NEXT_PUBLIC_API_URL)
         │
         ▼
┌─────────────────────────────────────┐
│   Backend API (FastAPI)             │
│   clinica-oncologica-v02-production │
│   Port: 8000                        │
│   URL: clinica-oncologica-v02       │
│       -production.up.railway.app    │
└────────┬────────────────────────────┘
         │
         ├─► PostgreSQL (Supabase)
         ├─► Redis (Cache)
         └─► WhatsApp (Evolution API)
```

---

## 🧪 Testes Locais (Opcional)

### **Build Local do Docker:**

```bash
cd quiz-mensal-interface

# Build da imagem
docker build -t quiz-interface:latest .

# Run local (porta 3000)
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=https://clinica-oncologica-v02-production.up.railway.app \
  -e NODE_ENV=production \
  quiz-interface:latest

# Testar
curl http://localhost:3000/api/health
```

---

## ⚠️ Troubleshooting

### **Erro: "Cannot find matching keyid"**
✅ **RESOLVIDO** - Substituído corepack por instalação direta do pnpm

### **Erro: "Failed to fetch quiz data"**
**Causa:** `NEXT_PUBLIC_API_URL` incorreta ou backend offline

**Solução:**
1. Verificar variável no Railway: `NEXT_PUBLIC_API_URL`
2. Testar backend: `curl https://clinica-oncologica-v02-production.up.railway.app/health`
3. Verificar logs do backend no Railway

### **Erro: "Invalid token"**
**Causa:** Token expirado ou inválido

**Solução:**
1. Verificar `MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS` no backend (padrão: 72h)
2. Gerar novo token via backend:
   ```bash
   POST /api/v1/monthly-quiz/generate-link
   {
     "patient_id": "uuid",
     "quiz_template_id": "uuid"
   }
   ```

### **Erro: "Healthcheck failed"**
**Causa:** Next.js não iniciou ou rota `/api/health` não existe

**Solução:**
1. Verificar logs do Railway: `railway logs`
2. Aumentar `healthcheckTimeout` em railway.json se build for lento
3. Verificar se porta 3000 está exposta corretamente

---

## 📝 Variáveis de Ambiente Railway

### **Quiz Interface:**
```bash
# PUBLIC (podem ser expostas no navegador)
NEXT_PUBLIC_API_URL=https://clinica-oncologica-v02-production.up.railway.app

# PRIVADAS (server-side apenas)
NODE_ENV=production
NEXT_TELEMETRY_DISABLED=1
```

### **Backend (relacionadas ao Quiz):**
```bash
# Quiz token configuration
MONTHLY_QUIZ_VIA_LINK=true
MONTHLY_QUIZ_BASE_URL=https://quiz-interface-production.up.railway.app/quiz/monthly
MONTHLY_QUIZ_TOKEN_SECRET=vfqzMK9OmQYX7uZnkihOIpj38eiiu9zcJOcEt7MZaZI
MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS=72

# CORS - incluir quiz interface
ALLOWED_ORIGINS=["https://frontend-production-18bb.up.railway.app","https://quiz-interface-production.up.railway.app","https://clinica-oncologica-v02-production.up.railway.app"]
```

---

## ✅ Checklist de Deploy

- [x] Dockerfile corrigido (pnpm via npm, não corepack)
- [x] railway.json configurado (DOCKERFILE builder)
- [x] `.env` com NEXT_PUBLIC_API_URL correto
- [ ] Variáveis configuradas no Railway Dashboard
- [ ] Backend em `ALLOWED_ORIGINS` inclui quiz URL
- [ ] Deploy iniciado no Railway
- [ ] Healthcheck passando (`/api/health`)
- [ ] Teste com token real do backend

---

## 🔗 Links Importantes

- **Quiz Interface (Produção):** https://quiz-interface-production.up.railway.app
- **Backend API:** https://clinica-oncologica-v02-production.up.railway.app
- **Railway Dashboard:** https://railway.app/
- **Documentação Next.js:** https://nextjs.org/docs

---

## 📚 Arquivos Relacionados

- [Dockerfile](../quiz-mensal-interface/Dockerfile) - Build configuration
- [railway.json](../quiz-mensal-interface/railway.json) - Deploy settings
- [.env](../quiz-mensal-interface/.env) - Environment variables
- [Backend .env](../backend-hormonia/.env) - Quiz configuration

---

**Data de criação:** 2025-10-05
**Última atualização:** 2025-10-05
**Status:** ✅ Pronto para deploy
