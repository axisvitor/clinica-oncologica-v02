# 🚨 RAILWAY - CORREÇÃO URGENTE DE VARIÁVEIS

## ❌ PROBLEMA ATUAL

**Logs mostram**:
```
API URL: https:clinica-oncologica-v02-production.up.railway.appapiv1
WS URL: wss:clinica-oncologica-v02-production.up.railway.appwsconnect
```

**O que está errado**:
- ❌ Sem `//` após `https:` e `wss:`
- ❌ Sem `/` antes de `api/v1` e `ws/connect`
- ❌ URLs coladas sem separadores

**Resultado**:
- Browser: `new URL()` falha → "Invalid URL"
- WebSocket: não conecta → loop infinito
- Login: travado em "carregando"

---

## ✅ CORREÇÃO IMEDIATA - PASSO A PASSO

### **ETAPA 1: Frontend Variables (Railway Dashboard)**

1. **Acesse Railway**: https://railway.app/
2. **Selecione o projeto**: `clinica-oncologica-v02`
3. **Clique no serviço**: `frontend-production-18bb`
4. **Aba**: `Variables`

#### **Variáveis para CORRIGIR** (copie exatamente):

**1. VITE_API_BASE_URL**
```
ANTES: https:clinica-oncologica-v02-production.up.railway.app
DEPOIS: https://clinica-oncologica-v02-production.up.railway.app
```

**2. VITE_API_URL**
```
ANTES: https:clinica-oncologica-v02-production.up.railway.appapiv1
DEPOIS: https://clinica-oncologica-v02-production.up.railway.app/api/v1
```

**3. VITE_API_BASE_PATH**
```
ANTES: /apiv1 ou apiv1
DEPOIS: /api/v1
```

**4. VITE_WS_BASE_URL**
```
ANTES: wss:clinica-oncologica-v02-production.up.railway.appwsconnect
DEPOIS: wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
```

**5. VITE_WS_URL**
```
ANTES: wss:clinica-oncologica-v02-production.up.railway.appwsconnect
DEPOIS: wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
```

#### **Como editar cada variável**:

1. Clique no **ícone de lápis** ✏️ ao lado da variável
2. **Delete** o valor antigo completamente
3. **Cole** o valor novo (DEPOIS) exatamente como está acima
4. Clique **fora da caixa** para salvar
5. **Repita** para todas as 5 variáveis

#### **Após editar todas**:
- Clique **"Save Changes"** (se aparecer)
- Railway vai **automaticamente redeploy**
- **Aguarde** status mudar para "Success" (2-3 minutos)

---

### **ETAPA 2: Backend Variables (Railway Dashboard)**

1. **Volte** para seleção de serviços
2. **Clique no serviço**: Backend principal
3. **Aba**: `Variables`

#### **Variável para CORRIGIR**:

**1. DATABASE_URL**
```
ANTES: postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres

DEPOIS: postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require
```

**⚠️ ATENÇÃO**:
- A **única diferença** é adicionar `?sslmode=require` no **final**
- **NÃO altere** nada antes disso
- **NÃO remova** a senha

#### **Como editar**:
1. Clique no **ícone de lápis** ✏️
2. Vá para o **final** da URL (após `/postgres`)
3. **Adicione**: `?sslmode=require`
4. Verifique que ficou: `...postgres?sslmode=require`
5. Clique **fora** para salvar

#### **Após editar**:
- Railway **redeploy automático**
- **Aguarde** status "Success"

---

### **ETAPA 3: Firebase Console (Enquanto aguarda deploys)**

1. **Acesse**: https://console.firebase.google.com/
2. **Projeto**: `sistema-oncologico-auth`
3. **Menu lateral**: `Authentication`
4. **Aba**: `Settings`
5. **Seção**: `Authorized domains`

#### **Adicionar domínios**:

1. Clique **"Add domain"**
2. Cole: `frontend-production-18bb.up.railway.app`
3. Clique **"Add"**
4. Repita:
   - Clique **"Add domain"**
   - Cole: `clinica-oncologica-v02-production.up.railway.app`
   - Clique **"Add"**

#### **Verificar lista final**:
- ✅ `localhost`
- ✅ `sistema-oncologico-auth.firebaseapp.com`
- ✅ `frontend-production-18bb.up.railway.app`
- ✅ `clinica-oncologica-v02-production.up.railway.app`

---

### **ETAPA 4: Testar (Após deploys concluídos)**

#### **4.1 Verificar Railway Builds**

**Frontend**:
- Railway Dashboard → `frontend-production-18bb` → `Deployments`
- Status deve estar: **"Success"** ✅
- Timestamp recente (após suas edições)

**Backend**:
- Railway Dashboard → Backend → `Deployments`
- Status deve estar: **"Success"** ✅
- Logs **SEM** erro: `SSL connection has been closed`

#### **4.2 Hard Refresh no Browser**

**Windows**:
```
Ctrl + Shift + R
ou
Ctrl + F5
```

**Mac**:
```
Cmd + Shift + R
```

**Alternativa**:
- Abra **aba anônima** (sempre pega versão fresh)

#### **4.3 DevTools - Network Tab**

1. Abra DevTools: `F12`
2. Aba **Network**
3. Recarregue página
4. Clique em **primeira linha** (HTML)
5. **Headers** → Verifique:
   ```
   Response Headers:
   Cache-Control: no-cache, no-store, must-revalidate
   ```

6. Verifique **arquivo JS principal**:
   ```
   ❌ ANTES: index-B7p7m4he.js
   ✅ DEPOIS: index-[novo-hash].js
   ```

#### **4.4 DevTools - Console Tab**

Aba **Console** deve mostrar:
```
✅ WebSocket connection established
✅ wss://clinica-oncologica-v02-production.up.railway.app/ws/connect?token=...

❌ NÃO DEVE TER:
❌ Invalid URL
❌ wss:clinica... (sem //)
```

#### **4.5 Teste Login Completo**

1. **Tela de login** deve carregar
2. Digite **credenciais válidas**
3. Clique **"Entrar"**
4. **Deve autenticar em 2-3 segundos** (não 40s)
5. **Dashboard carrega** normalmente
6. **Sem** loop de reconexão

---

## 🔍 VALIDAÇÃO PÓS-CORREÇÃO

### **Backend Logs (Esperado)**
```
✓ Database connected successfully
✓ Firebase Admin SDK initialized
✓ WebSocket manager initialized
REQUEST | GET /api/v1/auth/me | Status: 200 | Total: 0.234s
```

### **Frontend Console (Esperado)**
```
[Info] The app is running in production mode
[ApiClient] Setting auth token: { hasToken: true }
[WebSocket] Connection established
[AuthContext] User authenticated successfully
```

---

## ❌ SE AINDA NÃO FUNCIONAR

### **Problema: URLs ainda erradas**
**Causa**: Railway não salvou alterações
**Fix**:
1. Volte em Railway → Variables
2. Verifique que valores estão corretos
3. Force redeploy manual: Settings → "Redeploy"

### **Problema: SSL connection closed ainda aparece**
**Causa**: DATABASE_URL sem `?sslmode=require`
**Fix**:
1. Backend → Variables → DATABASE_URL
2. Vá até o final
3. Adicione `?sslmode=require`
4. Deve terminar: `...postgres?sslmode=require`

### **Problema: Login trava mesmo com URLs corretas**
**Causa**: Cache do browser
**Fix**:
1. Feche **todas** as abas do site
2. Limpe cache: Ctrl + Shift + Delete → "Cached images and files"
3. Abra **aba anônima**
4. Tente novamente

### **Problema: Firebase erro "domain not authorized"**
**Causa**: Domínios Railway não adicionados
**Fix**:
1. Firebase Console → Authentication → Settings
2. Authorized domains → Add domain
3. Adicione ambos domínios Railway

---

## 📋 CHECKLIST RÁPIDO

**Antes de testar, confirme**:

- [ ] Frontend VITE_API_URL tem `https://` e `/api/v1`
- [ ] Frontend VITE_WS_URL tem `wss://` e `/ws/connect`
- [ ] Backend DATABASE_URL tem `?sslmode=require` no final
- [ ] Railway builds mostram "Success"
- [ ] Firebase tem 4 domínios autorizados
- [ ] Hard refresh feito (Ctrl + Shift + R)

**Se TODOS marcados ✅ e ainda não funciona**:
- Compartilhe logs do Railway (frontend E backend)
- Compartilhe screenshot do DevTools Console

---

## 🎯 RESUMO VISUAL

```
┌─────────────────────────────────────────────────────┐
│ Railway → frontend-production-18bb → Variables      │
├─────────────────────────────────────────────────────┤
│ VITE_API_URL                                        │
│ https://clinica...railway.app/api/v1          [✏️] │
│                     ^^              ^^^^^^^^         │
│                   adicionar      adicionar          │
│                                                      │
│ VITE_WS_URL                                         │
│ wss://clinica...railway.app/ws/connect        [✏️] │
│     ^^                       ^^^^^^^^^^^            │
│   adicionar                 adicionar               │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Railway → backend → Variables                       │
├─────────────────────────────────────────────────────┤
│ DATABASE_URL                                        │
│ postgresql+psycopg://...postgres?sslmode=require    │
│                                 ^^^^^^^^^^^^^^^^^   │
│                                 adicionar no final  │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Firebase Console → Authentication → Settings        │
├─────────────────────────────────────────────────────┤
│ Authorized domains                                  │
│ • localhost                                    ✓    │
│ • sistema-oncologico-auth.firebaseapp.com     ✓    │
│ • frontend-production-18bb.up.railway.app     [+]  │
│ • clinica-oncologica-v02...railway.app        [+]  │
└─────────────────────────────────────────────────────┘
```

---

**Última atualização**: 2025-10-06
**Status**: 🚨 **AÇÃO IMEDIATA REQUERIDA**

**Após aplicar correções**: Sinalize para validação final! 🚀
