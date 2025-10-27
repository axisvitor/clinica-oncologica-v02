# 🔧 Troubleshooting: Tela Branca no Login (Produção)

## ⚠️ Problema
Tela branca aparece ao acessar a página de login em produção (Railway).

## 🎯 Causas Mais Comuns

### 1. **Variáveis de Ambiente do Firebase Não Configuradas** ⭐ MAIS COMUM
Firebase não consegue inicializar sem as variáveis corretas.

#### ✅ Solução:
Verificar e configurar no **Railway Dashboard** → **frontend-production** → **Variables**:

```bash
# Firebase Configuration (OBRIGATÓRIAS)
VITE_FIREBASE_API_KEY=AIzaSy...
VITE_FIREBASE_AUTH_DOMAIN=clinica-oncologica-v02.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=clinica-oncologica-v02
VITE_FIREBASE_STORAGE_BUCKET=clinica-oncologica-v02.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abc123
VITE_FIREBASE_MEASUREMENT_ID=G-XXXXXXXXXX (opcional)
```

**Como obter essas variáveis:**
1. Acesse [Firebase Console](https://console.firebase.google.com/)
2. Selecione o projeto `clinica-oncologica-v02`
3. Vá em **Project Settings** (ícone engrenagem) → **General**
4. Role até **Your apps** → Selecione o app Web
5. Copie os valores de `firebaseConfig`

#### 🔍 Como Verificar se Está Configurado:
```bash
# No Railway, clique em "Deploy Logs" e procure por:
[FirebaseLazy] Firebase configuration is incomplete
```

Se aparecer esse erro, as variáveis estão faltando.

---

### 2. **API Backend Não Disponível**
ConfigProvider não consegue se conectar ao backend.

#### ✅ Solução:
Verificar variáveis de API no Railway:

```bash
VITE_API_BASE_URL=https://clinica-oncologica-v02-production.up.railway.app
VITE_API_URL=https://clinica-oncologica-v02-production.up.railway.app/api/v1
```

**Testar se o backend está respondendo:**
```bash
curl https://clinica-oncologica-v02-production.up.railway.app/api/v1/health
# Deve retornar: {"status":"ok"}
```

---

### 3. **Build Incompleto ou com Erros**
Vite build falhou ou gerou chunks quebrados.

#### ✅ Solução:
Fazer **rebuild completo** no Railway:

1. Railway Dashboard → **frontend-production**
2. Clique em **"Deployments"**
3. Clique em **"Redeploy"** no deployment mais recente
4. Monitore os logs de build:
   ```
   ✓ built in 45.23s
   ✓ 123 modules transformed
   ```

Se o build não completar com sucesso, verifique:
- Dependências instaladas: `npm ci`
- TypeScript compilando sem erros
- Tailwind CSS processando corretamente

---

### 4. **Chunks JavaScript Quebrados**
class-variance-authority ou outro chunk crítico falhou ao carregar.

#### ✅ Solução:
Verificar no **Browser DevTools** (F12):

1. Abra a tab **Console**
2. Procure por erros como:
   ```
   Failed to load module script
   ChunkLoadError
   Cannot read properties of undefined
   ```

3. Abra a tab **Network**
4. Recarregue a página (F5)
5. Procure por arquivos `.js` com status **404** ou **ERR_CONNECTION_REFUSED**

**Se encontrar chunks 404:**
- Limpe o cache do browser (Ctrl+Shift+Delete)
- Faça rebuild no Railway
- Verifique se `dist/` está sendo gerado corretamente

---

### 5. **CSRF Token Falhando**
Requisição de token CSRF travando a inicialização.

#### ✅ Solução:
Agora o erro é **não-crítico** e não bloqueia mais o app.

Verifique nos logs do browser:
```
⚠️ [ConfigProvider] Step 3: Failed to fetch CSRF token (non-critical)
```

Se aparecer, o sistema continua funcionando normalmente.

---

## 🔍 Diagnóstico Passo a Passo

### Passo 1: Abrir DevTools
1. Pressione **F12** no browser
2. Vá para a tab **Console**
3. Recarregue a página (**F5**)

### Passo 2: Verificar Logs de Inicialização
Procure por essas mensagens na ordem:

```
🚀 [ConfigProvider] Starting configuration loading...
📋 [ConfigProvider] Step 1: Loading runtime configuration...
✅ [ConfigProvider] Step 1: Configuration loaded successfully
📡 [ConfigProvider] Step 2: Initializing API client...
✅ [ConfigProvider] Step 2: API client initialized
🔐 [ConfigProvider] Step 3: Fetching CSRF token...
✅ [ConfigProvider] Step 3: CSRF token fetched successfully
🔥 [ConfigProvider] Step 4: Using Firebase for authentication
✅ [ConfigProvider] Configuration initialization complete!
```

**Se travar em algum step:**
- **Step 1**: Problema nas variáveis de ambiente
- **Step 2**: Backend não está disponível
- **Step 3**: CSRF falhando (não-crítico)

### Passo 3: Verificar Erros Visuais
Com as correções aplicadas, você verá **overlay de erro vermelho** se algo falhar:

- **"⚠️ Erro de Configuração"** → Variáveis Firebase faltando
- **"⚠️ Erro Crítico"** → JavaScript quebrado
- **"⚠️ Erro de Promise"** → Async/await falhando

### Passo 4: Verificar Network Requests
Na tab **Network** do DevTools:

1. Filtre por **XHR/Fetch**
2. Procure por:
   - `/api/v1/health` → Deve retornar 200 OK
   - `/api/v1/csrf-token` → Deve retornar 200 OK
   - `/api/config` → Pode retornar 404 (não é crítico)

---

## 🚀 Solução Rápida (Checklist)

Siga essa ordem:

- [ ] **1. Verificar variáveis Firebase no Railway**
  ```bash
  VITE_FIREBASE_API_KEY=...
  VITE_FIREBASE_AUTH_DOMAIN=...
  VITE_FIREBASE_PROJECT_ID=...
  ```

- [ ] **2. Verificar backend rodando**
  ```bash
  curl https://clinica-oncologica-v02-production.up.railway.app/api/v1/health
  ```

- [ ] **3. Fazer redeploy no Railway**
  - Frontend → Deployments → Redeploy

- [ ] **4. Limpar cache do browser**
  - Ctrl+Shift+Delete → Limpar tudo

- [ ] **5. Testar em aba anônima**
  - Ctrl+Shift+N (Chrome) ou Ctrl+Shift+P (Firefox)

---

## 📊 Monitoramento em Produção

### Logs do Railway
```bash
# Ver logs do frontend
railway logs --service frontend-production

# Ver logs do backend
railway logs --service backend-production
```

### Console do Browser
Sempre verifique o console (F12) em produção para diagnosticar:
- Erros JavaScript
- Requisições falhando
- Promises rejeitadas

---

## 🔧 Correções Aplicadas

As seguintes melhorias foram implementadas para prevenir tela branca:

1. ✅ **Firebase Lazy Loader**: Mostra erro visual se variáveis faltarem
2. ✅ **ConfigProvider Timeout**: Força erro após 15s se travar
3. ✅ **Global Error Handlers**: Captura erros não tratados e mostra overlay
4. ✅ **CSRF Non-Critical**: Não bloqueia mais inicialização
5. ✅ **Enhanced Logging**: Logs detalhados em cada step

---

## 📞 Suporte

Se o problema persistir após seguir todos os passos:

1. **Capturar evidências:**
   - Screenshot da tela branca
   - Console do browser (F12)
   - Network requests (tab Network)
   - Logs do Railway

2. **Informar:**
   - URL que está falhando
   - Browser e versão
   - Horário exato do erro
   - Passos para reproduzir

---

## 🎯 Próximos Passos

Depois de resolver a tela branca:

1. **Monitorar performance:**
   - Tempo de carregamento inicial
   - Firebase initialization time
   - API response time

2. **Configurar alertas:**
   - Sentry para tracking de erros
   - Uptime monitoring (UptimeRobot)

3. **Melhorias futuras:**
   - Service Worker para offline
   - Skeleton screens durante loading
   - Progressive Web App (PWA)
