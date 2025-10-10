# CSRF Token Deduplication - Troubleshooting

**Date:** 2025-10-10
**Issue:** Frontend ainda enviando 3+ requisições CSRF apesar do fix estar commitado
**Status:** 🔍 INVESTIGANDO

---

## 🎯 Situação Atual

### ✅ Código Correto no Repositório
```bash
$ grep -n "csrfTokenPromise" frontend-hormonia/src/lib/api-client.ts
83:  private csrfTokenPromise: Promise<void> | null = null
150:    if (this.csrfTokenPromise) {
152:      return this.csrfTokenPromise
156:    this.csrfTokenPromise = (async () => {
176:        this.csrfTokenPromise = null
```

### ❌ Railway Logs Ainda Mostrando 3+ Requisições
```
GET /api/v1/csrf-token - 200 (request 1)
GET /api/v1/csrf-token - 200 (request 2)
GET /api/v1/csrf-token - 200 (request 3)
GET /api/v1/csrf-token - 200 (request 4)
GET /api/v1/csrf-token - 200 (request 5)
GET /api/v1/csrf-token - 200 (request 6)
```

---

## 🔍 Possíveis Causas

### 1. Cache do Build do Vite no Railway ✅ TENTAMOS RESOLVER
**O que fizemos:**
- Criado `.railwayignore` para ignorar cache do Vite
- Forçado rebuild com `railway up --service frontend`
- Commit: `8e66637`

**Status:** Railway pode ainda estar usando build antigo

### 2. Cache do CDN/Browser 🔍 INVESTIGAR
**Problema:**
- JavaScript bundle pode estar em cache do browser
- CDN do Railway pode ter versão antiga em cache
- Service Worker pode estar servindo versão antiga

### 3. Build não Completou ⏳ AGUARDANDO
**Problema:**
- Railway pode ainda estar buildando
- Build pode ter falhado silenciosamente
- Deploy pode não ter sido acionado

---

## 🔧 Soluções para Testar

### Solução 1: Limpar Cache do Browser (PRIORITÁRIO)

**Teste em Modo Anônimo:**
```
1. Abra navegador em modo anônimo (Ctrl+Shift+N)
2. Acesse: https://frontend-production-18bb.up.railway.app
3. F12 → Network tab
4. Filtre por "csrf-token"
5. Recarregue a página
6. Verifique quantas requisições aparecem
```

**Esperado:**
- ✅ Apenas 1 requisição se cache do browser era o problema
- ❌ Ainda 3+ requisições se é problema do Railway build

**Limpar Cache Completo:**
```
1. Ctrl+Shift+Delete
2. Selecione "Todo o período"
3. Marque "Imagens e arquivos em cache"
4. Marque "Dados de sites e cookies"
5. Clique "Limpar dados"
6. Recarregue a aplicação
```

---

### Solução 2: Verificar Build do Railway

**Verificar Último Deploy:**
```bash
railway logs --service frontend | grep -E "(build|Build|npm|vite)" | tail -50
```

**Procurar por:**
- ✅ `vite v` - Versão do Vite sendo usada
- ✅ `build complete` - Build completou com sucesso
- ✅ `dist/assets/index-XXXXX.js` - Hash do bundle mudou
- ❌ `error` ou `failed` - Build falhou

**Verificar Service Workers:**
```javascript
// No console do browser (F12 → Console)
navigator.serviceWorker.getRegistrations().then(function(registrations) {
 for(let registration of registrations) {
    console.log('Service Worker:', registration);
    registration.unregister(); // Remove service worker
 }
});
```

---

### Solução 3: Forçar Rebuild Completo com Cache Busting

**Opção A: Adicionar Cache-Busting ao index.html**
```html
<!-- frontend-hormonia/index.html -->
<script>
  // Force reload on version mismatch
  const APP_VERSION = '2.0.1'; // Increment this
  if (localStorage.getItem('app_version') !== APP_VERSION) {
    localStorage.setItem('app_version', APP_VERSION);
    window.location.reload(true);
  }
</script>
```

**Opção B: Adicionar Build Timestamp**
```typescript
// frontend-hormonia/vite.config.ts
export default defineConfig({
  define: {
    '__BUILD_TIME__': JSON.stringify(new Date().toISOString())
  }
})
```

**Opção C: Modificar package.json version**
```bash
cd frontend-hormonia
npm version patch  # Incrementa versão (ex: 1.0.1 → 1.0.2)
git add package.json
git commit -m "chore: Bump version to force Railway rebuild"
git push origin sprint2-hive-mind-implementation
```

---

### Solução 4: Verificar se Railway Está Usando Branch Correta

**Verificar configuração do Railway:**
```bash
# No Railway dashboard:
1. Vá para Settings → Environment
2. Verifique "Branch": deve ser "sprint2-hive-mind-implementation"
3. Se estiver em "main" ou "docs-refactor-py313", mude para sprint2
```

**Verificar último commit deployado:**
```bash
# No Railway logs, procure por:
"Deploying commit: [hash]"

# Deve ser um destes commits:
- 8e66637 (Force clean build)
- 7aa8263 (CSRF deduplication)
- 2bc29a4 (Latest)
```

---

### Solução 5: Invalidar Cache do CDN/Railway

**Railway pode estar cacheando assets estáticos:**

**Forçar nova versão dos assets:**
```typescript
// frontend-hormonia/vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        // Gera novos hashes para todos os arquivos
        entryFileNames: `assets/[name]-[hash]-${Date.now()}.js`,
        chunkFileNames: `assets/[name]-[hash]-${Date.now()}.js`,
        assetFileNames: `assets/[name]-[hash]-${Date.now()}.[ext]`
      }
    }
  }
})
```

---

## 🧪 Teste Definitivo: Inspecionar Bundle JavaScript

**1. Via DevTools:**
```
1. F12 → Sources tab
2. Encontre "index-XXXXX.js" (arquivo principal)
3. Ctrl+F e procure por "csrfTokenPromise"
4. Verifique se encontra a lógica de deduplicação:
   - if (this.csrfTokenPromise) {
   - return this.csrfTokenPromise
```

**Se NÃO encontrar:** Railway está servindo build antigo!
**Se ENCONTRAR:** Problema é em outro lugar (browser cache ou lógica)

**2. Via curl (verificar hash do bundle):**
```bash
curl -s https://frontend-production-18bb.up.railway.app/ | grep -o 'index-[^"]*\.js'
```

**Anote o hash** (ex: `index-abc123def.js`)

**Depois do rebuild:**
```bash
curl -s https://frontend-production-18bb.up.railway.app/ | grep -o 'index-[^"]*\.js'
```

**Se hash mudou:** Novo build deployado ✅
**Se hash igual:** Build não foi atualizado ❌

---

## 📊 Diagnóstico Completo

| Check | Como Verificar | Status |
|-------|----------------|--------|
| Código no repo | ✅ `grep csrfTokenPromise` | ✅ Correto |
| Commit pushado | ✅ `git log` | ✅ 7aa8263 |
| .railwayignore | ✅ Existe | ✅ Criado |
| Railway branch | Railway dashboard | ⏳ Verificar |
| Build completou | `railway logs` | ⏳ Verificar |
| Bundle hash | `curl + grep` | ⏳ Verificar |
| Browser cache | Modo anônimo | ⏳ Testar |
| Service Worker | Console check | ⏳ Verificar |

---

## ✅ Passo a Passo Recomendado

### 1. PRIMEIRO: Teste Rápido (2 minutos)
```bash
# Abra modo anônimo e teste
# Se funcionar (1 requisição) → Era cache do browser!
# Se não funcionar (3+ requisições) → Continue investigando
```

### 2. Verificar Railway (5 minutos)
```bash
# Check branch, último commit, e logs de build
railway logs --service frontend | grep -E "(build|error)" | tail -20
```

### 3. Forçar Rebuild se Necessário (10 minutos)
```bash
cd frontend-hormonia
npm version patch
git add package.json
git commit -m "chore: Force Railway rebuild - bump version"
git push origin sprint2-hive-mind-implementation
railway up --service frontend
```

### 4. Aguardar Build e Testar (5-10 minutos)
```bash
# Aguardar Railway completar
# Limpar cache do browser
# Testar novamente
```

---

## 🎯 Resultado Esperado Final

**Browser DevTools → Network:**
```
GET /api/v1/csrf-token - 200 (APENAS 1 requisição!)
```

**Railway Logs:**
```
[ApiClient] Initiating CSRF token fetch... (1x)
[ApiClient] CSRF token fetch already in progress, waiting... (2x)
[ApiClient] CSRF token fetched successfully (1x)

GET /api/v1/csrf-token - 200 (1 única requisição no backend!)
```

---

## 📞 Suporte

Se após todas as tentativas ainda ver 3+ requisições:

1. **Capture evidências:**
   - Screenshot do Network tab
   - Output de `curl | grep index-`
   - Railway logs do build

2. **Verifique código no bundle:**
   - DevTools → Sources → Procure `csrfTokenPromise`
   - Se não estiver lá, o build está incorreto

3. **Última opção: Deploy manual:**
   ```bash
   cd frontend-hormonia
   npm run build
   # Verificar dist/assets/index-*.js manualmente
   # Confirmar que csrfTokenPromise está no código
   ```

---

**Status:** 🔍 Aguardando testes do usuário
**Próximo passo:** Testar em modo anônimo PRIMEIRO
**Confiança:** 🟡 MÉDIA (código correto, mas Railway pode estar cacheando)
