# 🚀 Variáveis de Ambiente para Railway - Frontend Hormonia

**Data de verificação:** 2025-10-04
**Status Supabase MCP:** ✅ Configuração validada

---

## ⚡ VARIÁVEIS CRÍTICAS (OBRIGATÓRIAS)

### 1. Supabase (Validado via MCP)
```bash
VITE_SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJzenB5cHl0ZGNpZ2d5YmJwbnJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkzMDQ0NzksImV4cCI6MjA2NDg4MDQ3OX0.qF_byaebH1q78a6SYhGfCuGSotF523o1ZqTrwOBkPYg
VITE_SUPABASE_AUTH_ENABLED=true
VITE_SUPABASE_REALTIME_ENABLED=true
```

### 2. Backend API (Railway Internal Network)
```bash
VITE_API_URL=http://clinica-oncologica-v02.railway.internal
VITE_API_BASE_PATH=/api/v1
VITE_API_TIMEOUT=30000
VITE_WS_URL=ws://clinica-oncologica-v02.railway.internal/ws
```

### 3. Firebase (Opcional - usa Mock Auth se não configurado)
```bash
VITE_FIREBASE_API_KEY=<sua-api-key-do-firebase-console>
VITE_FIREBASE_AUTH_DOMAIN=<seu-projeto>.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<seu-projeto-id>
VITE_FIREBASE_STORAGE_BUCKET=<seu-projeto>.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=<sender-id-numerico>
VITE_FIREBASE_APP_ID=1:123456789:web:abc123def456
VITE_FIREBASE_MEASUREMENT_ID=G-XXXXXXXXXX
```

**⚠️ IMPORTANTE:** Se Firebase não for configurado, o sistema usa Mock Auth automaticamente.

---

## 🔧 VARIÁVEIS DE CONFIGURAÇÃO

### Autenticação & Segurança
```bash
VITE_USE_MOCK_AUTH=true
VITE_SESSION_TIMEOUT=3600000
VITE_TOKEN_REFRESH_THRESHOLD=300000
VITE_JWT_STORAGE_KEY=hormonia_access_token
VITE_JWT_REFRESH_KEY=hormonia_refresh_token
VITE_ENABLE_CSP=true
VITE_FORCE_HTTPS=true
VITE_SECURITY_HEADERS_ENABLED=true
```

### Ambiente & Debug
```bash
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
VITE_APP_NAME=Hormonia - Sistema de Gestão Oncológica
VITE_APP_VERSION=2.0.0
```

### Features Habilitadas
```bash
VITE_ENABLE_WHATSAPP_INTEGRATION=true
VITE_ENABLE_AI_CHAT=true
VITE_ENABLE_APPOINTMENT_BOOKING=true
VITE_ENABLE_PATIENT_PORTAL=true
VITE_ENABLE_TELEMEDICINE=true
VITE_ENABLE_DARK_MODE=true
VITE_ENABLE_EVOLUTION=true
VITE_ENABLE_DEBUG_TOOLS=false
VITE_ENABLE_MOCK_DATA=false
VITE_USE_MOCK_API=false
```

### AI Features
```bash
VITE_AI_CHAT_ENABLED=true
VITE_AI_ANALYTICS_ENABLED=true
VITE_AI_INSIGHTS_ENABLED=true
VITE_AI_RECOMMENDATIONS_ENABLED=true
```

---

## 📦 VARIÁVEIS DE PERFORMANCE

### Upload & Files
```bash
VITE_MAX_FILE_SIZE=10485760
VITE_ALLOWED_FILE_TYPES=pdf,doc,docx,jpg,jpeg,png,gif,txt
VITE_UPLOAD_CHUNK_SIZE=1048576
VITE_SUPPORTED_FILE_TYPES=image/jpeg,image/png,image/gif,application/pdf
```

### HTTP & Cache
```bash
VITE_REQUEST_TIMEOUT=30000
VITE_REQUEST_RETRY_ATTEMPTS=3
VITE_REQUEST_RETRY_DELAY=1000
VITE_CACHE_DURATION=300000
VITE_IMAGE_CACHE_DURATION=3600000
```

### Paginação
```bash
VITE_DEFAULT_PAGE_SIZE=20
VITE_MAX_PAGE_SIZE=100
```

---

## 🎨 VARIÁVEIS DE UI

### Layout
```bash
VITE_SIDEBAR_WIDTH=280
VITE_HEADER_HEIGHT=64
VITE_FOOTER_HEIGHT=60
```

### Cores (Opcional - usa Tailwind defaults)
```bash
VITE_PRIMARY_COLOR=
VITE_SECONDARY_COLOR=
VITE_SUCCESS_COLOR=
VITE_ERROR_COLOR=
VITE_WARNING_COLOR=
```

---

## 🌍 VARIÁVEIS DE INTERNACIONALIZAÇÃO

```bash
VITE_DEFAULT_LANGUAGE=pt-BR
VITE_SUPPORTED_LANGUAGES=pt-BR,en-US
VITE_TIMEZONE=America/Sao_Paulo
VITE_DATE_FORMAT=DD/MM/YYYY
VITE_TIME_FORMAT=HH:mm
VITE_DATETIME_FORMAT=DD/MM/YYYY HH:mm
```

---

## 📱 VARIÁVEIS DE INTEGRAÇÃO

### WhatsApp
```bash
VITE_WHATSAPP_INSTANCE_NAME=hormonia-instance
VITE_WHATSAPP_MAX_FILE_SIZE=16777216
```

### Monitoramento (Opcional)
```bash
VITE_ENABLE_ERROR_REPORTING=true
VITE_ENABLE_PERFORMANCE_MONITORING=true
VITE_SENTRY_DSN=
VITE_ANALYTICS_TRACKING_ID=
VITE_GOOGLE_ANALYTICS_ID=
VITE_HOTJAR_ID=
VITE_MIXPANEL_TOKEN=
```

### Mapas (Opcional)
```bash
VITE_GOOGLE_MAPS_API_KEY=
VITE_MAPBOX_TOKEN=
```

---

## 🏥 VARIÁVEIS DE CLÍNICA

```bash
VITE_CLINIC_NAME=Clínica Hormonia
VITE_CLINIC_ADDRESS=Rua das Flores, 123, São Paulo, SP
VITE_CLINIC_PHONE=+55 11 99999-9999
VITE_CLINIC_EMAIL=contato@clinicahormonia.com.br
```

---

## 🚀 VARIÁVEIS DE BUILD

```bash
VITE_BUILD_SOURCEMAP=false
VITE_BUILD_MINIFY=true
VITE_BUILD_TARGET=es2015
VITE_BASE_URL=/
VITE_ASSET_INLINE_LIMIT=4096
VITE_CSS_CODE_SPLIT=true
```

---

## 📋 VARIÁVEIS PWA

```bash
VITE_PWA_ENABLED=true
VITE_PWA_SHORT_NAME=Hormonia
VITE_PWA_DESCRIPTION=Sistema de Gestão para Clínica Oncológica
VITE_PWA_THEME_COLOR=
VITE_PWA_BACKGROUND_COLOR=
```

---

## 🔍 VARIÁVEIS DE HEALTH CHECK

```bash
VITE_HEALTH_CHECK_INTERVAL=60000
VITE_API_STATUS_CHECK=true
VITE_SHOW_VERSION=false
```

---

## ⚙️ COMO CONFIGURAR NO RAILWAY

### 1. Acesse o Projeto
```
Railway Dashboard → Seu Projeto Frontend → Variables
```

### 2. Adicione as Variáveis Críticas PRIMEIRO
Copie e cole as variáveis da seção "VARIÁVEIS CRÍTICAS" acima.

### 3. Adicione as Demais Conforme Necessário
As outras seções são opcionais e podem ser adicionadas gradualmente.

### 4. Redeploy
Após adicionar as variáveis, faça redeploy do serviço.

---

## ⚠️ NOTAS IMPORTANTES

### Firebase
- Se você NÃO configurar Firebase, o sistema automaticamente usa **Mock Auth**
- Para usar Firebase, configure TODAS as 7 variáveis de Firebase
- **NÃO** use placeholders como `${VAR}` - Vite lê como string literal

### Vite Build-Time vs Runtime
- Vite substitui `import.meta.env.VITE_*` em **build time**
- Railway define variáveis em `process.env`
- **Problema**: Vite NÃO lê `process.env` automaticamente
- **Solução atual**: Sistema usa fallbacks inteligentes

### Variáveis Sensíveis
Estas variáveis **NUNCA** devem ser commitadas no git:
- `VITE_SUPABASE_ANON_KEY`
- `VITE_FIREBASE_*`
- `VITE_SENTRY_DSN`
- API keys de serviços externos

---

## 🐛 Troubleshooting

### Erro: "Supabase configuration validation failed"
**Causa:** Variáveis Supabase não estão sendo carregadas corretamente.

**Solução:**
1. Verifique se `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY` estão no Railway
2. Redeploy após adicionar
3. Verifique logs do build: deve aparecer `VITE_SUPABASE_URL=[SET]`

### Erro: "Firebase configuration is incomplete"
**Causa:** Firebase tentando inicializar sem credenciais.

**Solução:**
1. Configure TODAS as variáveis Firebase
2. **OU** deixe vazias - sistema usa Mock Auth automaticamente

### Tela Branca
**Causa:** Erro no carregamento de configuração.

**Solução:**
1. Verifique se variáveis críticas estão configuradas
2. Olhe console do navegador para detalhes
3. Sistema agora tem fallbacks - não deve mais dar tela branca

---

## 📝 Checklist de Deploy

- [ ] Supabase URL configurada
- [ ] Supabase Anon Key configurada
- [ ] Backend API URL configurada (Railway internal)
- [ ] Firebase configurado OU VITE_USE_MOCK_AUTH=true
- [ ] VITE_ENVIRONMENT=production
- [ ] VITE_DEBUG_MODE=false
- [ ] Redeploy realizado
- [ ] Logs do build verificados
- [ ] Aplicação testada no navegador

---

**Última atualização:** 2025-10-04 via Supabase MCP
**Validação:** ✅ Credenciais Supabase verificadas e corretas
