# Guia de Seguranca - Sistema Hormonia

**Versao:** 2.0
**Data:** 2025-12-26
**Conformidade:** LGPD, HIPAA, OWASP Top 10

---

## Pontuacao de Seguranca: 8.7/10

| Componente | Pontuacao | Status |
|------------|-----------|--------|
| Protecao CSRF | 9.2/10 | Excelente |
| Configuracao CORS | 9.0/10 | Excelente |
| Autenticacao Firebase | 8.5/10 | Bom |
| Rate Limiting | 8.0/10 | Bom |
| Seguranca de Cache | 9.0/10 | Excelente |

---

## 1. Autenticacao Firebase

### Fluxo

```
1. Cliente faz login no Firebase (frontend)
2. Firebase retorna ID Token (JWT)
3. Cliente envia token no header Authorization
4. Backend valida token com Firebase Admin SDK
5. Backend cria sessao Redis (2-5ms)
6. Cliente usa session cookie para requisicoes subsequentes
```

### Validacao de Firebase UID

```python
# Padrao: alfanumerico, 20-128 caracteres
_FIREBASE_UID_PATTERN = re.compile(r'^[A-Za-z0-9]{20,128}$')
```

---

## 2. Sessoes Redis

| Atributo | Valor | Proposito |
|----------|-------|-----------|
| httpOnly | True | Previne XSS |
| secure | True (prod) | Apenas HTTPS |
| sameSite | strict | Previne CSRF |
| max_age | 86400s | 24h expiracao |

**Latencia:** 2-5ms (vs 200-500ms com Firebase)

---

## 3. Protecao CSRF

### Padrao Double Submit Cookie

```
Formato: {timestamp}.{random_hex_64}.{hmac_signature}
Entropia: 256 bits (HMAC-SHA256)
Throughput: 272,276 tokens/segundo
```

### Endpoints Isentos

- `/health`
- `/api/v2/auth/csrf-token`
- `/api/v2/auth/login`
- `/webhooks/*`

---

## 4. CORS

### Regras de Producao

- Sem wildcard (*)
- HTTPS obrigatorio
- Lista explicita de origens
- Fail-fast validation

```python
allow_headers=[
    "Content-Type",
    "Authorization",
    "X-CSRF-Token",
]
```

---

## 5. Rate Limiting

| Endpoint | Rate | Per |
|----------|------|-----|
| /auth/login | 5 | 60s |
| /auth/register | 3 | 300s |
| /api/v2/* | 100 | 60s |
| /ai/* | 10 | 60s |

**Algoritmo:** Token Bucket com Redis

---

## 6. Headers de Seguranca

- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy: default-src 'self'`
- `Referrer-Policy: strict-origin-when-cross-origin`

---

## 7. Conformidade LGPD

### Dados Criptografados

| Campo | Metodo | Busca |
|-------|--------|-------|
| CPF | AES-256-GCM | SHA-256 hash |
| Telefone | AES-256-GCM | SHA-256 hash |
| Email | AES-256-GCM | - |

### Soft Delete

Todos os dados de pacientes usam soft delete para retencao legal.

---

## 8. Checklist de Producao

### Ambiente
- [ ] `APP_ENVIRONMENT=production`
- [ ] `APP_ENABLE_DEBUG=False`
- [ ] Segredos com 32+ caracteres

### Autenticacao
- [ ] Firebase credentials configuradas
- [ ] Redis sessions habilitadas
- [ ] CSRF secret key com alta entropia

### Rede
- [ ] HTTPS habilitado
- [ ] CORS sem wildcards
- [ ] Rate limiting com Redis

---

## 9. Arquivos de Referencia

| Arquivo | Funcao |
|---------|--------|
| `app/middleware/csrf.py` | Protecao CSRF |
| `app/core/cors.py` | Configuracao CORS |
| `app/middleware/rate_limiter.py` | Rate limiting |
| `app/middleware/security_headers.py` | Headers OWASP |
| `app/dependencies/auth_dependencies.py` | Autenticacao |

---

**Ultima Atualizacao:** 2025-12-26
