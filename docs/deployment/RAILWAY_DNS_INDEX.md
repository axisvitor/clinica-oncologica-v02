# 📚 Índice: Documentação Railway DNS Error

## 🎯 Começar Aqui

### Para Resolver RÁPIDO (3-5 minutos)
👉 **[RAILWAY_DNS_QUICK_FIX.md](./RAILWAY_DNS_QUICK_FIX.md)** ⭐
- Soluções rápidas passo a passo
- 3 cenários principais
- Fix em minutos

### Para Entender o Problema
👉 **[RAILWAY_DNS_EXECUTIVE_SUMMARY.md](./RAILWAY_DNS_EXECUTIVE_SUMMARY.md)**
- Resumo executivo
- Status atual e próximos passos
- Decisões estratégicas

---

## 📖 Documentação Técnica

### 1. Análise Completa
**[RAILWAY_DNS_ERROR_ANALYSIS.md](./RAILWAY_DNS_ERROR_ANALYSIS.md)**
- Análise técnica detalhada do erro
- Causa raiz identificada
- Soluções disponíveis (4 opções)
- Referências e best practices

**Quando usar:**
- Precisa entender o problema em profundidade
- Quer conhecer todas as opções disponíveis
- Busca referências técnicas

---

### 2. Guia de Networking
**[RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md)**
- Como funciona networking no Railway
- Diferenças: Docker Compose vs Railway
- Private Networking explicado
- Service Discovery e DNS
- Configuração de variáveis de ambiente
- Troubleshooting completo

**Quando usar:**
- Primeira vez usando Railway
- Quer entender como conectar serviços
- Precisa configurar comunicação frontend ↔ backend
- Troubleshooting de problemas de rede

---

### 3. Checklist Detalhado
**[RAILWAY_DNS_FIX_CHECKLIST.md](./RAILWAY_DNS_FIX_CHECKLIST.md)**
- Checklist passo a passo completo
- 4 cenários de solução
- Testes de validação
- Diagnóstico estruturado

**Quando usar:**
- Quer seguir um processo estruturado
- Precisa validar cada etapa
- Troubleshooting sistemático
- Documentar decisões tomadas

---

## 🛠️ Ferramentas

### Scripts de Diagnóstico

#### 1. Diagnostic Tool
**Arquivo:** `frontend-hormonia/railway-dns-diagnostic.sh`

```bash
# Executar diagnóstico completo
./railway-dns-diagnostic.sh
```

**O que faz:**
- ✅ Verifica variáveis de ambiente
- ✅ Testa resolução DNS
- ✅ Testa conectividade backend
- ✅ Analisa nginx.conf processado
- ✅ Sugere soluções específicas

---

#### 2. Config Switcher
**Arquivo:** `frontend-hormonia/switch-nginx-config.sh`

```bash
# Alternar para configuração completa (com backend)
./switch-nginx-config.sh full

# Alternar para fallback (sem backend)
./switch-nginx-config.sh fallback

# Executar diagnóstico
./switch-nginx-config.sh diagnostic
```

**O que faz:**
- ✅ Alterna entre nginx.conf e nginx.conf.fallback
- ✅ Atualiza Dockerfile automaticamente
- ✅ Gera instruções de commit/deploy

---

### Configurações Alternativas

#### 1. nginx.conf (Padrão)
**Arquivo:** `frontend-hormonia/nginx.conf`

**Quando usar:**
- Backend está deployado no Railway
- Comunicação via Private Networking
- Produção completa

**Requer:**
- `BACKEND_HOST=[service].railway.internal`
- `BACKEND_PORT=8000`

---

#### 2. nginx.conf.fallback
**Arquivo:** `frontend-hormonia/nginx.conf.fallback`

**Quando usar:**
- Backend não está disponível
- Quer servir apenas frontend
- Troubleshooting/debug

**Comportamento:**
- ✅ Frontend funciona (HTML, CSS, JS)
- ✅ Healthcheck passa
- ❌ `/api/*` retorna 503
- ❌ WebSocket desabilitado

---

## 🚀 Guias por Cenário

### Cenário 1: Backend ESTÁ no Railway

**Documentos relevantes:**
1. [RAILWAY_DNS_QUICK_FIX.md](./RAILWAY_DNS_QUICK_FIX.md#solução-1-backend-está-no-railway) → Solução 1
2. [RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md#método-1-private-networking) → Private Networking

**Passos:**
```bash
# 1. Identificar nome do backend
# Railway Dashboard → Services → [copiar nome]

# 2. Configurar variável
BACKEND_HOST=[nome-do-backend].railway.internal
BACKEND_PORT=8000

# 3. Deploy automático
```

---

### Cenário 2: Backend em URL Externa

**Documentos relevantes:**
1. [RAILWAY_DNS_QUICK_FIX.md](./RAILWAY_DNS_QUICK_FIX.md#solução-2-backend-em-url-externa) → Solução 2
2. [RAILWAY_DNS_FIX_CHECKLIST.md](./RAILWAY_DNS_FIX_CHECKLIST.md#cenário-c-backend-em-url-externapública) → Cenário C

**Passos:**
```bash
# 1. Configurar variável com URL pública
BACKEND_HOST=api.seusite.com
BACKEND_PORT=443

# 2. Configurar CORS no backend
CORS_ORIGINS=https://seu-frontend.railway.app

# 3. Deploy
```

---

### Cenário 3: Sem Backend (Temporário)

**Documentos relevantes:**
1. [RAILWAY_DNS_QUICK_FIX.md](./RAILWAY_DNS_QUICK_FIX.md#solução-3-desabilitar-backend-temporariamente) → Solução 3
2. [RAILWAY_DNS_FIX_CHECKLIST.md](./RAILWAY_DNS_FIX_CHECKLIST.md#cenário-d-backend-não-disponível---servir-apenas-frontend) → Cenário D

**Passos:**
```bash
# 1. Usar config switcher
./switch-nginx-config.sh fallback

# 2. Commit e push
git add frontend-hormonia/Dockerfile
git commit -m "fix: usar nginx fallback sem backend"
git push

# 3. Railway redeploy automático
```

---

## 📊 Fluxograma de Decisão

```
┌─────────────────────────────────────┐
│  Erro: host not found in upstream   │
│         "backend:8000"              │
└──────────────┬──────────────────────┘
               │
               ▼
        ┌──────────────┐
        │ Backend está │
        │  no Railway? │
        └──────┬───────┘
               │
       ┌───────┴────────┐
       │                │
      SIM              NÃO
       │                │
       ▼                ▼
   ┌────────┐      ┌──────────┐
   │Solução │      │Backend em│
   │   1    │      │  outro   │
   │        │      │  local?  │
   │Private │      └────┬─────┘
   │Network │           │
   └────────┘      ┌────┴─────┐
                   │          │
                  SIM        NÃO
                   │          │
                   ▼          ▼
              ┌────────┐  ┌────────┐
              │Solução │  │Solução │
              │   2    │  │   3    │
              │        │  │        │
              │Public  │  │Fallback│
              │  URL   │  │ Config │
              └────────┘  └────────┘
```

**Onde buscar ajuda:**
- Solução 1 → [RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md)
- Solução 2 → [RAILWAY_DNS_FIX_CHECKLIST.md](./RAILWAY_DNS_FIX_CHECKLIST.md)
- Solução 3 → [RAILWAY_DNS_QUICK_FIX.md](./RAILWAY_DNS_QUICK_FIX.md)

---

## 🔍 Troubleshooting por Sintoma

### "host not found in upstream"
📖 **Leitura recomendada:**
1. [RAILWAY_DNS_QUICK_FIX.md](./RAILWAY_DNS_QUICK_FIX.md) (começar aqui)
2. [RAILWAY_DNS_ERROR_ANALYSIS.md](./RAILWAY_DNS_ERROR_ANALYSIS.md#análise-do-problema)
3. [RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md#troubleshooting-dns)

🛠️ **Ferramentas:**
- `./railway-dns-diagnostic.sh` (diagnóstico automático)

---

### "Connection refused"
📖 **Leitura recomendada:**
1. [RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md#erro-connection-refused)
2. [RAILWAY_DNS_FIX_CHECKLIST.md](./RAILWAY_DNS_FIX_CHECKLIST.md#fase-1-verificar-backend)

🛠️ **Ações:**
- Verificar status do backend no Railway
- Validar healthcheck do backend
- Testar porta correta

---

### "upstream timed out"
📖 **Leitura recomendada:**
1. [RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md#erro-upstream-timed-out)

🛠️ **Ações:**
- Aumentar timeouts no nginx.conf
- Verificar performance do backend
- Analisar logs do backend

---

### "502 Bad Gateway"
📖 **Leitura recomendada:**
1. [RAILWAY_DNS_ERROR_ANALYSIS.md](./RAILWAY_DNS_ERROR_ANALYSIS.md#investigação-necessária)
2. [RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md#conectar-servicos)

🛠️ **Ações:**
- Verificar backend está rodando
- Validar BACKEND_HOST correto
- Testar conectividade manual

---

## 📈 Progressão Sugerida

### Nível 1: Iniciante (Fix Rápido)
1. **[RAILWAY_DNS_QUICK_FIX.md](./RAILWAY_DNS_QUICK_FIX.md)**
2. **[RAILWAY_DNS_EXECUTIVE_SUMMARY.md](./RAILWAY_DNS_EXECUTIVE_SUMMARY.md)**
3. Scripts: `./switch-nginx-config.sh`

**Tempo:** 5-15 minutos

---

### Nível 2: Intermediário (Entendimento)
1. **[RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md)**
2. **[RAILWAY_DNS_FIX_CHECKLIST.md](./RAILWAY_DNS_FIX_CHECKLIST.md)**
3. Scripts: `./railway-dns-diagnostic.sh`

**Tempo:** 30-45 minutos

---

### Nível 3: Avançado (Expertise)
1. **[RAILWAY_DNS_ERROR_ANALYSIS.md](./RAILWAY_DNS_ERROR_ANALYSIS.md)**
2. **[RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md)** (completo)
3. Customizar configs para casos específicos

**Tempo:** 1-2 horas

---

## 🎓 Recursos de Aprendizado

### Conceitos Fundamentais
📖 [RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md#como-funciona)
- Docker Compose vs Railway
- Private Networking
- Service Discovery
- DNS interno

### Best Practices
📖 [RAILWAY_DNS_ERROR_ANALYSIS.md](./RAILWAY_DNS_ERROR_ANALYSIS.md#referências-railway)
- Networking no Railway
- Configuração de variáveis
- Segurança e performance

### Troubleshooting Avançado
📖 [RAILWAY_DNS_FIX_CHECKLIST.md](./RAILWAY_DNS_FIX_CHECKLIST.md#testes-de-validação)
- Diagnóstico sistemático
- Testes de validação
- Soluções por cenário

---

## 📞 Suporte

### Documentação Oficial
- [Railway Private Networking](https://docs.railway.app/guides/private-networking)
- [Railway Environment Variables](https://docs.railway.app/guides/variables)
- [Railway Service Networking](https://docs.railway.app/reference/networking)

### Ferramentas de Debug
```bash
# Dentro do container (Railway Shell)
nslookup [hostname]          # DNS lookup
dig [hostname]               # DNS detalhado
curl http://[host]:[port]    # Teste HTTP
netstat -tuln                # Portas listening
ps aux | grep nginx          # Processos nginx
```

### Logs Relevantes
- Railway Dashboard → Frontend → Deployments → Logs
- Railway Dashboard → Backend → Deployments → Logs
- Buscar por: "BACKEND_HOST", "upstream", "dns"

---

## ✅ Checklist de Resolução Completa

### Diagnóstico
- [ ] Executar `./railway-dns-diagnostic.sh`
- [ ] Ler [RAILWAY_DNS_EXECUTIVE_SUMMARY.md](./RAILWAY_DNS_EXECUTIVE_SUMMARY.md)
- [ ] Identificar cenário (1, 2 ou 3)

### Implementação
- [ ] Escolher solução apropriada
- [ ] Seguir guia relevante:
  - Solução 1: [RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md)
  - Solução 2: [RAILWAY_DNS_FIX_CHECKLIST.md](./RAILWAY_DNS_FIX_CHECKLIST.md)
  - Solução 3: [RAILWAY_DNS_QUICK_FIX.md](./RAILWAY_DNS_QUICK_FIX.md)
- [ ] Configurar variáveis/modificar configs
- [ ] Commit e push (se necessário)

### Validação
- [ ] Aguardar redeploy
- [ ] Verificar logs (sem erros DNS)
- [ ] Validar healthcheck (passing)
- [ ] Testar frontend (carrega)
- [ ] Testar API (se backend disponível)

### Documentação
- [ ] Documentar solução aplicada
- [ ] Registrar decisões tomadas
- [ ] Atualizar runbook se necessário

---

## 📝 Contribuir

Encontrou um caso não coberto? Tem sugestões?

**Adicionar nova solução:**
1. Documentar em [RAILWAY_DNS_ERROR_ANALYSIS.md](./RAILWAY_DNS_ERROR_ANALYSIS.md)
2. Criar cenário em [RAILWAY_DNS_FIX_CHECKLIST.md](./RAILWAY_DNS_FIX_CHECKLIST.md)
3. Atualizar índice

**Melhorias:**
- Issues/PRs bem-vindos
- Compartilhar casos de uso
- Sugerir ferramentas adicionais

---

## 📊 Resumo Visual

```
┌─────────────────────────────────────────────────────┐
│          RAILWAY DNS ERROR - DOCUMENTAÇÃO           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  🚀 QUICK START                                     │
│  ├─ RAILWAY_DNS_QUICK_FIX.md        (5 min)        │
│  └─ RAILWAY_DNS_EXECUTIVE_SUMMARY.md (resumo)      │
│                                                     │
│  📖 GUIAS TÉCNICOS                                  │
│  ├─ RAILWAY_DNS_ERROR_ANALYSIS.md   (análise)      │
│  ├─ RAILWAY_NETWORKING_GUIDE.md     (networking)   │
│  └─ RAILWAY_DNS_FIX_CHECKLIST.md    (checklist)    │
│                                                     │
│  🛠️ FERRAMENTAS                                     │
│  ├─ railway-dns-diagnostic.sh       (diagnóstico)  │
│  ├─ switch-nginx-config.sh          (configs)      │
│  ├─ nginx.conf                      (com backend)  │
│  └─ nginx.conf.fallback             (sem backend)  │
│                                                     │
│  📚 ESTE DOCUMENTO                                  │
│  └─ RAILWAY_DNS_INDEX.md            (navegação)    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

**Última atualização:** 2025-10-04
**Versão:** 1.0
**Mantido por:** DevOps Team

---

**🎯 Próximo passo:** Abra [RAILWAY_DNS_QUICK_FIX.md](./RAILWAY_DNS_QUICK_FIX.md) para começar!
