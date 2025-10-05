# 🚨 AÇÃO NECESSÁRIA: Substituir URL do Backend Railway

## ⚠️ Status Atual

O arquivo `.env` foi atualizado com **URL placeholder**:
```bash
VITE_API_BASE_URL="https://backend-hormonia-production.up.railway.app"
VITE_API_URL="https://backend-hormonia-production.up.railway.app/api/v1"
VITE_WS_URL="wss://backend-hormonia-production.up.railway.app/ws"
```

**VOCÊ PRECISA** substituir `backend-hormonia-production.up.railway.app` pela **URL real** do seu backend no Railway.

## 📍 Como Obter a URL Real do Backend

### Método 1: Railway Dashboard (Recomendado)

1. Acesse [Railway Dashboard](https://railway.app/)
2. Abra seu projeto **clinica-oncologica-v02**
3. Clique no serviço **backend-hormonia**
4. Vá em **Settings** → **Networking** → **Public Networking**
5. Copie o domínio (exemplo: `backend-hormonia-production-abc123.up.railway.app`)

### Método 2: Via Railway CLI

Se tiver Railway CLI instalado:

```bash
cd "c:\Meu Projetos\clinica-oncologica-v02"
railway status
```

Procure pela linha do backend e copie o domínio.

### Método 3: Verificar no Próprio Railway

1. No Railway Dashboard, com o projeto aberto
2. Olhe na lista de serviços
3. O backend deve mostrar um ícone de globo 🌐 com a URL

## ✏️ Como Substituir no .env

### Opção A: Editar Manualmente

Abra o arquivo `.env` e substitua **3 linhas**:

```bash
# Linha 14 - API Base URL
VITE_API_BASE_URL="https://SEU-BACKEND-REAL.up.railway.app"

# Linha 16 - API URL com /api/v1
VITE_API_URL="https://SEU-BACKEND-REAL.up.railway.app/api/v1"

# Linha 24 e 25 - WebSocket URLs
VITE_WS_BASE_URL="wss://SEU-BACKEND-REAL.up.railway.app/ws"
VITE_WS_URL="wss://SEU-BACKEND-REAL.up.railway.app/ws"
```

### Opção B: Usar Busca e Substituir (VSCode)

1. Abra `.env` no VSCode
2. Pressione `Ctrl+H` (Find and Replace)
3. **Find**: `backend-hormonia-production.up.railway.app`
4. **Replace**: `SEU-BACKEND-REAL.up.railway.app`
5. Clique em "Replace All"

## ✅ Como Validar se a URL Está Correta

Após substituir, teste no navegador:

```bash
# 1. Teste se o backend responde (substitua pela sua URL)
https://SEU-BACKEND-REAL.up.railway.app/api/v1/health

# Deve retornar algo como:
{
  "status": "healthy",
  "timestamp": "2025-01-05T..."
}

# 2. Se der erro 404 ou timeout, a URL está errada
```

## 📝 Exemplo Real

**Antes** (placeholder):
```bash
VITE_API_BASE_URL="https://backend-hormonia-production.up.railway.app"
```

**Depois** (URL real que você copiou do Railway):
```bash
VITE_API_BASE_URL="https://backend-hormonia-production-7a2f9b.up.railway.app"
```

## 🚀 Após Substituir

1. **Salve** o arquivo `.env`
2. **Commit** as alterações:
   ```bash
   git add frontend-hormonia/.env
   git commit -m "fix: Update Railway backend URL to public domain"
   git push
   ```
3. **Redeploy** no Railway (ele vai pegar automaticamente)

## ⚠️ Importante

- ❌ **NÃO USE** `.railway.internal` - só funciona entre serviços Railway
- ✅ **USE** `.up.railway.app` - URL pública acessível do navegador
- ✅ **USE** `https://` para API e `wss://` para WebSocket

## 🆘 Se Não Souber a URL

Se você realmente não conseguir encontrar a URL do backend:

1. Vá no Railway Dashboard
2. No serviço backend, clique em **Settings**
3. Role até **Domains**
4. Se não tiver domínio, clique em **Generate Domain**
5. Railway vai criar uma URL pública automaticamente

---

**Após fazer isso, o sistema vai funcionar em produção!** 🎉
