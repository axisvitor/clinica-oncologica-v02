# CORS Essential Mode - Simplified Configuration

**Data:** 2025-01-10
**Versão:** 2.1.0 (Essential)
**Status:** ✅ Active

---

## 📋 Overview

Esta configuração implementa o **CORS Essential Mode** - uma abordagem minimalista focada em estabilidade e simplicidade, removendo complexidades desnecessárias.

### 🎯 Filosofia

- **Menos é Mais:** Apenas o essencial para funcionar
- **Bearer Tokens:** Sem cookies, sem `credentials`
- **Mínimo de Headers:** `Authorization` e `Content-Type` apenas
- **Máxima Estabilidade:** Menos preflights, menos pontos de falha

---

## ⚙️ Configuração Atual

**Arquivo:** [backend-hormonia/app/core/middleware_setup.py](../backend-hormonia/app/core/middleware_setup.py:105-112)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,      # Lista explícita de origens
    allow_credentials=False,                      # ✅ SEM cookies (usa Bearer)
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],  # ✅ Apenas essencial
    max_age=86400                                # Cache preflight 24h
)
```

### ✅ O que INCLUI

| Parâmetro | Valor | Justificativa |
|-----------|-------|---------------|
| `allow_origins` | Lista explícita | Segurança: apenas domínios permitidos |
| `allow_credentials` | `False` | Frontend usa `Authorization: Bearer` |
| `allow_methods` | 6 métodos explícitos | Suporta operações CRUD + OPTIONS |
| `allow_headers` | `Authorization`, `Content-Type` | Mínimo necessário para API REST |
| `max_age` | 86400 (24h) | Cache de preflight reduz requisições |

### ❌ O que NÃO inclui

| Removido | Razão |
|----------|-------|
| `allow_credentials=True` | Não usa cookies, apenas Bearer tokens |
| `expose_headers` | Headers customizados não acessíveis ao JS (aceitável) |
| Headers customizados em `allow_headers` | `X-Request-ID`, `X-Quiz-Token`, etc. removidos |

---

## 🔄 Comparação: Antes vs Depois

### **Configuração Anterior (Robusta)**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,                    # ❌ Cookies habilitados
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[                            # ❌ 13 headers
        "Authorization", "Content-Type", "Accept",
        "X-Request-ID", "X-Correlation-ID", "X-Quiz-Token",
        "X-Patient-ID", "X-Monthly-Quiz-Token", "X-Session-ID",
        "X-Requested-With", "Accept-Language", "Content-Language",
        "Cache-Control", "Pragma"
    ],
    expose_headers=[                           # ❌ 11 headers expostos
        "X-Request-ID", "X-Correlation-ID", "X-Process-Time",
        "X-Quiz-Session-ID", "X-Quiz-Progress", "X-RateLimit-Limit",
        "X-RateLimit-Remaining", "X-RateLimit-Reset", "X-Query-Count",
        "X-DB-Time-Ms", "X-Request-Duration"
    ],
    max_age=86400
)
```

### **Configuração Atual (Essential)**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,                   # ✅ Sem cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],  # ✅ 2 headers
    max_age=86400
)
```

### 📊 Redução de Complexidade

| Métrica | Antes | Depois | Redução |
|---------|-------|--------|---------|
| `allow_headers` | 13 headers | 2 headers | **-85%** |
| `expose_headers` | 11 headers | 0 headers | **-100%** |
| Credenciais | Sim | Não | **Simplificado** |
| Preflights complexos | Alta | Baixa | **Menos requisições** |

---

## 🧪 Compatibilidade com Frontend

### **Frontend React (Vite)**

**Arquivo:** [frontend-hormonia/src/lib/api-client.ts](../frontend-hormonia/src/lib/api-client.ts)

```typescript
// ✅ COMPATÍVEL: Usa Authorization Bearer, não cookies
const response = await fetch(url, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,  // ✅ Funciona sem credentials
  },
  body: JSON.stringify(data),
});
```

**Sem `credentials: 'include'`** → Não precisa de `allow_credentials=True`

### **Quiz Next.js**

**Arquivo:** [quiz-mensal-interface/lib/api.ts](../quiz-mensal-interface/lib/api.ts)

```typescript
// ✅ COMPATÍVEL: Também usa headers, não cookies
const response = await fetch(url, {
  headers: {
    'Content-Type': 'application/json',
  },
});
```

---

## ⚠️ Limitações Conhecidas

### 1. **Headers Customizados Não Acessíveis**

**Impacto:** JavaScript no frontend **não** pode ler headers customizados via `response.headers.get()`:

```javascript
// ❌ NÃO FUNCIONA (headers não expostos)
const requestId = response.headers.get('X-Request-ID');  // null
const processTime = response.headers.get('X-Process-Time');  // null
```

**Mitigação:** Se precisar de métricas/IDs, retorne no **corpo da resposta**:

```json
{
  "data": {...},
  "meta": {
    "requestId": "abc123",
    "processTime": 0.245
  }
}
```

### 2. **Sem Suporte a Cookies**

**Impacto:** Se futuramente o sistema precisar de cookies (sessões):

```javascript
// ❌ NÃO FUNCIONA (credentials=False)
fetch(url, {
  credentials: 'include',  // Não permitido
});
```

**Mitigação:** Manter Bearer tokens (abordagem atual) ou migrar para **Opção B** (credentials=True).

---

## 🎯 Quando Usar Essential Mode

### ✅ **Use Essential Mode quando:**

1. Frontend usa **Bearer tokens** (não cookies)
2. Não precisa ler **headers customizados** no JavaScript
3. Prioriza **estabilidade** sobre features avançadas
4. Quer **menos preflights** e complexidade
5. Tem problemas de **502/conectividade** (reduzir superfície de falha)

### ❌ **NÃO use Essential Mode quando:**

1. Sistema depende de **cookies** para autenticação
2. Frontend precisa ler **headers de rate limiting** (`X-RateLimit-*`)
3. Precisa expor **IDs de correlação** (`X-Request-ID`) para debugging
4. Sistema usa **sessions** ao invés de tokens

---

## 🔄 Migração para Configuração Robusta (se necessário)

Se no futuro precisar voltar para configuração com credenciais:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,  # ⚠️ Habilitar cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization", "Content-Type",
        "X-Request-ID", "X-Quiz-Token",  # ⚠️ Re-adicionar headers
    ],
    expose_headers=[
        "X-Request-ID", "X-Process-Time",  # ⚠️ Expor headers
    ],
    max_age=86400
)
```

---

## 📊 Testes

**Arquivo:** [tests/backend/test_cors_smoke.py](../tests/backend/test_cors_smoke.py)

Testes atualizados para Essential Mode:

```python
def test_credentials_disabled(self, base_url: str):
    """Valida que credentials está desabilitado"""
    response = requests.options(...)
    assert response.headers.get("Access-Control-Allow-Credentials") != "true"

def test_allowed_headers_essential(self, base_url: str):
    """Valida apenas Authorization e Content-Type"""
    # Apenas 2 headers permitidos
```

**Executar testes:**
```bash
pytest tests/backend/test_cors_smoke.py -v
```

---

## 🔒 Segurança

### ✅ Mantém Segurança Essencial

- ✅ Origens explícitas (não wildcard em produção)
- ✅ Métodos HTTP explícitos (não wildcard)
- ✅ Sem credenciais = menos superfície de ataque
- ✅ Apenas headers essenciais permitidos

### ⚠️ Trade-offs Aceitáveis

- Headers customizados não acessíveis ao JS (mitigado via corpo da resposta)
- Sem cookies (design atual já usa Bearer tokens)

---

## 📝 Checklist de Validação

### Validação Rápida

```bash
# 1. Preflight de origem permitida
curl -X OPTIONS https://seu-backend.railway.app/api/v1/health \
  -H "Origin: https://seu-frontend.railway.app" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization, content-type" \
  -v

# Esperado:
# ✅ Access-Control-Allow-Origin: https://seu-frontend.railway.app
# ✅ Access-Control-Allow-Headers: authorization, content-type
# ❌ Access-Control-Allow-Credentials: NÃO deve estar presente ou ser "false"

# 2. GET real com origem permitida
curl https://seu-backend.railway.app/api/v1/health \
  -H "Origin: https://seu-frontend.railway.app" \
  -v

# Esperado:
# ✅ Access-Control-Allow-Origin presente
```

---

## 🎯 Próximos Passos

1. **Deploy em produção** após validação local
2. **Monitorar logs** para erros CORS
3. **Testar frontend** em produção
4. **Se estável por 7 dias** → considerar permanente
5. **Se problemas** → avaliar retornar para configuração robusta

---

**Modo:** Essential (Simplified)
**Foco:** Estabilidade > Features
**Status:** ✅ Ativo
**Última Atualização:** 2025-01-10
