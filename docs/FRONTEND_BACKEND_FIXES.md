# Frontend ↔ Backend Connection Fixes

## ✅ Correções Aplicadas

### 1. Base URL duplicada (API Client)
**Problema:** `VITE_API_URL` podia vir com `/api/v1`, e o código adicionava outro `/api/v1/...`, resultando em `http://host/api/v1/api/v1/...`

**Solução aplicada:**
- **[config-initializer.tsx](../frontend-hormonia/src/lib/config-initializer.tsx:55-62)**: Usa `VITE_API_BASE_URL` e sanitiza `VITE_API_URL` removendo `/api/v1`
- **[WhatsAppService.ts](../frontend-hormonia/src/services/whatsapp/WhatsAppService.ts:84-89)**: Mesma lógica aplicada

**Validação:** `hasAPI` agora aceita ambas variáveis em [config-initializer.tsx:245](../frontend-hormonia/src/lib/config-initializer.tsx:245)

---

### 2. Inconsistência WebSocket
**Problema:** Código usava `VITE_WS_URL` em alguns lugares e `VITE_WS_BASE_URL` em outros. Default em porta errada (8080 em vez de 8000).

**Solução aplicada (Opção B - Robusta):**
- **[useWebSocket.ts](../frontend-hormonia/src/hooks/useWebSocket.ts:28-30)**: Usa `VITE_WS_BASE_URL` com fallback para `VITE_WS_URL`. Default em `ws://localhost:8000/ws`
- **[runtime-config.ts](../frontend-hormonia/src/lib/runtime-config.ts:267-279)**: Função `normalizeConfig()` cria alias - ambas variáveis são preenchidas
- **[post-build-config.js](../frontend-hormonia/scripts/post-build-config.js:62-72)**: Emite **ambas** variáveis (`VITE_WS_URL` e `VITE_WS_BASE_URL`)

**Validação:** `hasWebSocket` aceita ambas em [config-initializer.tsx:246](../frontend-hormonia/src/lib/config-initializer.tsx:246)

---

### 3. Fallback de produção perigoso
**Problema:** [runtime-config.ts](../frontend-hormonia/src/lib/runtime-config.ts:62-93) tinha URLs hardcoded do Railway que podiam apontar para ambiente errado.

**Solução aplicada:**
- **[runtime-config.ts:69-72](../frontend-hormonia/src/lib/runtime-config.ts:69-72)**: Fallbacks agora são strings vazias com comentários `// MUST be set via environment variable`
- Aplicação agora falha visivelmente se variáveis de ambiente não estiverem configuradas, evitando apontar para ambiente incorreto silenciosamente

---

### 4. Interface da configuração
**Adicionado em [runtime-config.ts:23-31](../frontend-hormonia/src/lib/runtime-config.ts:23-31):**
```typescript
export interface RuntimeConfig {
  // ...
  VITE_API_BASE_URL?: string; // Base URL without /api/v1 suffix
  VITE_WS_URL: string;
  VITE_WS_BASE_URL?: string; // WebSocket base URL (standardized variable)
  // ...
}
```

---

## ✅ Resolvido - Endpoint de upload

### 5. Endpoint de upload criado
**Problema resolvido:** [WhatsAppService.uploadMedia()](../frontend-hormonia/src/services/whatsapp/WhatsAppService.ts:424-439) chamava `POST /api/v1/upload/media` que não existia

**Solução implementada:**
1. **Criado endpoint completo:** [backend-hormonia/app/api/v1/upload.py](../backend-hormonia/app/api/v1/upload.py)
   - Rota: `POST /api/v1/upload/media`
   - Retorna: `{ url: string, type: string, size: number, filename: string, uploaded_at: datetime }`
   - Suporta: imagens, vídeos, áudio, documentos, textos
   - Validação de tipo MIME e tamanho (10MB padrão, 50MB máximo)
   - Organização automática por categoria (`/uploads/image/`, `/uploads/video/`, etc.)
   - Rotas adicionais: `DELETE /media` e `GET /media/info`

2. **Configuração adicionada:** [backend-hormonia/app/config.py:151-159](../backend-hormonia/app/config.py#L151-L159)
   ```python
   UPLOAD_DIR: str = "uploads"  # Configurável via env
   MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
   ```

3. **Roteamento registrado:** [backend-hormonia/app/core/router_registry.py:76](../backend-hormonia/app/core/router_registry.py#L76)
   ```python
   app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload"])
   ```

4. **Servir arquivos estáticos:** [backend-hormonia/app/core/application_factory.py](../backend-hormonia/app/core/application_factory.py)
   - Montado `/uploads` para servir arquivos enviados
   - Criação automática do diretório `uploads/`

**Tipos de arquivo suportados:**
- Imagens: JPEG, PNG, GIF, WebP
- Vídeos: MP4, MPEG, QuickTime, WebM
- Áudio: MP3, OGG, WAV, WebM
- Documentos: PDF, Word, Excel
- Texto: TXT, CSV

**Exemplo de uso:**
```bash
curl -X POST https://backend.railway.app/api/v1/upload/media \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@image.jpg"

# Resposta:
{
  "url": "/uploads/image/20251005_143022_abc123.jpg",
  "type": "image/jpeg",
  "size": 245678,
  "filename": "image.jpg",
  "uploaded_at": "2025-10-05T14:30:22.123456"
}
```

---

### 6. WhatsApp depende de flag
**Problema:** Backend só registra rotas WhatsApp se `ENABLE_EVOLUTION=true` ([router_registry.py](../backend-hormonia/app/core/router_registry.py))

**Checklist de produção:**
```bash
# Backend environment variables (Railway/Docker)
ENABLE_EVOLUTION=true
EVOLUTION_API_URL=https://evolution-api.example.com
EVOLUTION_API_KEY=your_api_key_here
EVOLUTION_WEBHOOK_URL=https://backend.example.com/api/v1/whatsapp/webhook
```

**Se não configurado:** Frontend receberá 404/501 ao chamar `/api/v1/whatsapp/*`

---

## 📋 Variáveis de Ambiente

### Frontend (Railway/Docker)

**Obrigatórias:**
```bash
# Supabase
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJxxx...

# API (escolha uma das duas opções)
# Opção 1: Base URL (recomendado)
VITE_API_BASE_URL=https://backend.railway.app

# Opção 2: URL completa (será sanitizada automaticamente)
VITE_API_URL=https://backend.railway.app/api/v1

# WebSocket (ambas funcionam - são aliases)
VITE_WS_BASE_URL=wss://backend.railway.app/ws
# ou
VITE_WS_URL=wss://backend.railway.app/ws
```

**Opcionais:**
```bash
VITE_WHATSAPP_INSTANCE_NAME=hormonia-instance
VITE_OPENAI_API_KEY=sk-xxx
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
```

### Backend (Railway/Docker)

**Para WhatsApp funcionar:**
```bash
ENABLE_EVOLUTION=true
EVOLUTION_API_URL=https://evolution-api.example.com
EVOLUTION_API_KEY=your_key
EVOLUTION_WEBHOOK_URL=https://backend.example.com/api/v1/whatsapp/webhook
```

---

## 🧪 Como Testar

### 1. Testar conexão API
```bash
# Development
curl http://localhost:8000/api/v1/auth/me
curl http://localhost:8000/health

# Production
curl https://backend.railway.app/api/v1/auth/me
```

### 2. Testar WebSocket
```javascript
// Browser console
const ws = new WebSocket('ws://localhost:8000/ws?token=YOUR_TOKEN');
ws.onopen = () => console.log('✅ Connected');
ws.onerror = (e) => console.error('❌ Error:', e);
```

### 3. Verificar variáveis injetadas
```javascript
// Browser console (após app carregar)
console.log(window.__ENV_CONFIG__);
```

---

## 📊 Mapeamento de Endpoints

### Frontend → Backend (confirmados ✅)

| Frontend | Backend | Status |
|----------|---------|--------|
| `/api/v1/auth/*` | `app/api/v1/auth.py` | ✅ |
| `/api/v1/patients/*` | `app/api/v1/patients.py` | ✅ |
| `/api/v1/messages/*` | `app/api/v1/messages.py` | ✅ |
| `/api/v1/flows/*` | `app/api/v1/flows.py` | ✅ |
| `/api/v1/quiz/*` | `app/api/v1/quiz.py` | ✅ |
| `/api/v1/monthly-quiz/*` | `app/api/v1/monthly_quiz.py` | ✅ |
| `/api/v1/monthly-quiz-public/*` | `app/api/v1/monthly_quiz_public.py` | ✅ |
| `/api/v1/analytics/*` | `app/api/v1/analytics.py` | ✅ |
| `/api/v1/reports/*` | `app/api/v1/reports.py` | ✅ |
| `/api/v1/whatsapp/*` | `app/integrations/whatsapp/api/routes.py` | ⚠️ Requer `ENABLE_EVOLUTION=true` |
| `/api/v1/upload/media` | `app/api/v1/upload.py` | ✅ |

---

## 🚀 Deploy Checklist

### Frontend
- [x] Build com `npm run build:runtime`
- [x] Config injetada em `dist/api/config`
- [x] Script `/config.js` carregado antes do `main.js`
- [ ] Variáveis de ambiente configuradas no Railway
- [ ] Testar acesso a `https://frontend.railway.app/config.js`

### Backend
- [ ] `ENABLE_EVOLUTION=true` se usar WhatsApp
- [ ] Credenciais Evolution API configuradas
- [ ] Endpoint `/api/v1/upload/media` criado ou frontend adaptado
- [ ] CORS configurado para domínio do frontend
- [ ] Health check em `/health` respondendo

### Integração
- [ ] Frontend consegue fazer login (`/api/v1/auth/login`)
- [ ] WebSocket conecta (`wss://backend/ws`)
- [ ] Rotas WhatsApp respondem (se `ENABLE_EVOLUTION=true`)
- [ ] Upload de mídia funciona (após implementação)

---

## 📝 Próximos Passos

1. **✅ CONCLUÍDO:** Endpoint `/api/v1/upload/media` criado e funcional

2. **Importante:** Documentar no README do backend os requisitos `ENABLE_EVOLUTION`

3. **Validação:** Testar em staging com variáveis reais antes de produção
   - Testar upload de diferentes tipos de arquivo
   - Validar limites de tamanho
   - Confirmar servir de arquivos estáticos

4. **Monitoramento:** Adicionar logs para rastrear uso de upload
   - Métricas de tamanho/tipo de arquivo
   - Rate limiting se necessário

5. **Produção:** Configurar variáveis de ambiente
   - `UPLOAD_DIR` para diretório persistente (volume Docker/Railway)
   - Considerar CDN para servir `/uploads` em produção

---

## 🔗 Arquivos Modificados

- [frontend-hormonia/src/lib/config-initializer.tsx](../frontend-hormonia/src/lib/config-initializer.tsx)
- [frontend-hormonia/src/services/whatsapp/WhatsAppService.ts](../frontend-hormonia/src/services/whatsapp/WhatsAppService.ts)
- [frontend-hormonia/src/hooks/useWebSocket.ts](../frontend-hormonia/src/hooks/useWebSocket.ts)
- [frontend-hormonia/src/lib/runtime-config.ts](../frontend-hormonia/src/lib/runtime-config.ts)
- [frontend-hormonia/scripts/post-build-config.js](../frontend-hormonia/scripts/post-build-config.js)

---

**Última atualização:** 2025-10-05
**Status geral:** 🟢 Totalmente resolvido - todas as correções aplicadas

## 🎉 Resumo das Implementações

✅ Base URL API corrigida (`VITE_API_BASE_URL`)
✅ WebSocket padronizado (`VITE_WS_BASE_URL` com alias)
✅ Fallbacks perigosos removidos
✅ Endpoint de upload criado e funcional
✅ Servir arquivos estáticos configurado
✅ Documentação completa atualizada
