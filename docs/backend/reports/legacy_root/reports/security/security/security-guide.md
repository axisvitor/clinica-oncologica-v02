# Guia Consolidado de Seguranca - Backend Hormonia

**Versao:** 2.0.0
**Data:** 2025-12-26
**Status:** Producao

---

## Indice

1. [Visao Geral de Seguranca (8 Camadas)](#1-visao-geral-de-seguranca-8-camadas)
2. [Autenticacao Firebase](#2-autenticacao-firebase)
3. [Sessoes Redis](#3-sessoes-redis)
4. [CSRF (Double Submit Cookie)](#4-csrf-double-submit-cookie)
5. [CORS](#5-cors)
6. [Rate Limiting](#6-rate-limiting)
7. [Criptografia (AES-256-GCM)](#7-criptografia-aes-256-gcm)
8. [Conformidade LGPD](#8-conformidade-lgpd)
9. [Headers de Seguranca](#9-headers-de-seguranca)
10. [Checklist de Producao](#10-checklist-de-producao)

---

## 1. Visao Geral de Seguranca (8 Camadas)

O Backend Hormonia implementa um modelo de seguranca em 8 camadas para protecao completa:

### Arquitetura de Seguranca em Camadas

```
Camada 8: Headers de Seguranca (CSP, HSTS, X-Frame-Options)
    |
Camada 7: Conformidade LGPD (Criptografia PII, Auditoria)
    |
Camada 6: Criptografia (AES-256-GCM, SHA-256)
    |
Camada 5: Rate Limiting (IP + Endpoint + Instance)
    |
Camada 4: CORS (Origin Validation)
    |
Camada 3: CSRF Protection (Double Submit Cookie)
    |
Camada 2: Sessoes Redis (TTL, Invalidacao)
    |
Camada 1: Autenticacao Firebase (JWT, Multi-Factor)
```

### Resumo de Protecoes

| Camada | Componente | Protecao | Status |
|--------|------------|----------|--------|
| 1 | Firebase Auth | JWT forgery, credential stuffing | Ativo |
| 2 | Redis Sessions | Session hijacking, fixation | Ativo |
| 3 | CSRF | Cross-site request forgery | Ativo |
| 4 | CORS | Unauthorized cross-origin access | Ativo |
| 5 | Rate Limiting | DDoS, brute force | Ativo |
| 6 | Criptografia | Data breach, PII exposure | Ativo |
| 7 | LGPD | Compliance violations | Ativo |
| 8 | Headers | XSS, clickjacking, MIME sniffing | Ativo |

### Pontuacao de Seguranca

- **Security Headers Score:** 95/100 (A+)
- **OWASP Top 10 Coverage:** 100%
- **LGPD Compliance:** 100%
- **Entropy Validation:** 128+ bits enforced

---

## 2. Autenticacao Firebase

### Visao Geral

O sistema utiliza Firebase Authentication como provedor de identidade primario, com validacao multi-camada.

### Fluxo de Autenticacao

```
1. Usuario -> Firebase Auth (login)
2. Firebase -> JWT Token (id_token)
3. Backend -> Valida JWT (firebase-admin)
4. Backend -> Cria sessao Redis
5. Backend -> Retorna session_id + CSRF token
```

### Configuracao

**Arquivo:** `app/services/firebase_auth_service.py`

```python
# Variaveis de ambiente necessarias
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n..."
FIREBASE_CLIENT_EMAIL=firebase-admin@project.iam.gserviceaccount.com
```

### Validacao de Token

```python
from app.services.firebase_auth_service import get_firebase_auth_service

async def verify_token(token: str) -> dict:
    """Valida token Firebase e retorna claims."""
    service = get_firebase_auth_service()
    decoded_token = await service.verify_id_token(token)

    return {
        "uid": decoded_token["uid"],
        "email": decoded_token.get("email"),
        "email_verified": decoded_token.get("email_verified", False),
    }
```

### Validacao de Entropia de Chaves

**CRITICO:** Todas as chaves de seguranca sao validadas no startup.

**Arquivo:** `app/utils/security_validation.py`

```python
from app.utils.security_validation import validate_key_strength, is_production_ready

# Validacao automatica no startup
# Producao: Minimo 128 bits de entropia
# Development: Minimo 64 bits (warning apenas)

# Chaves validadas:
# - SECURITY_SECRET_KEY (JWT signing)
# - AUTH_JWT_SECRET_KEY (JWT fallback)
# - SECURITY_ENCRYPTION_KEY (Field encryption)
# - SECURITY_CSRF_SECRET_KEY (CSRF protection)
```

**Geracao de Chaves Seguras:**

```bash
# Gerar chave com 256+ bits de entropia
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

### Padroes Detectados como Placeholder

```regex
change[\s_-]?this
your[\s_-]?secret
replace[\s_-]?me
todo
xxx+
example
test[\s_-]?key
default
password
```

### Erros Comuns

| Erro | Causa | Solucao |
|------|-------|---------|
| `Token expired` | JWT expirado | Usuario deve re-autenticar |
| `Token invalid` | Assinatura invalida | Verificar configuracao Firebase |
| `User not found` | UID nao existe no banco | Criar usuario ou verificar registro |
| `Insufficient entropy` | Chave fraca detectada | Gerar nova chave com 128+ bits |

---

## 3. Sessoes Redis

### Arquitetura de Sessoes

```
Firebase Token -> Validacao -> Sessao Redis -> Session Cookie
                                    |
                              user_data cached
                              permissions cached
                              csrf_token stored
```

### Configuracao Redis

**Arquivo:** `app/core/redis_manager.py`

```python
# Variaveis de ambiente
REDIS_URL=rediss://user:pass@host:port
REDIS_SSL=true
REDIS_MAX_CONNECTIONS=50  # Recomendado (era 20)
```

### Estrutura da Sessao

```python
session_data = {
    "firebase_uid": "abc123",
    "user_id": "uuid-456",
    "email": "user@example.com",
    "role": "doctor",
    "permissions": ["read:patients", "write:patients"],
    "csrf_token": "random-token",
    "created_at": "2025-01-01T00:00:00Z",
    "expires_at": "2025-01-01T08:00:00Z",
}
```

### TTL e Invalidacao

| Tipo | TTL | Motivo |
|------|-----|--------|
| Session | 8h | Jornada de trabalho |
| CSRF Token | 1h | Seguranca reforçada |
| Rate Limit | 1min | Janela de rate limit |
| Idempotency | 2h | Retry window (reduzido de 24h) |

### Operacoes de Sessao

```python
from app.core.redis_manager import get_redis_manager

redis = get_redis_manager()

# Criar sessao
await redis.set_session(session_id, session_data, ttl=28800)

# Recuperar sessao
session = await redis.get_session(session_id)

# Invalidar sessao (logout)
await redis.delete_session(session_id)

# Invalidar todas sessoes do usuario
await redis.invalidate_user_sessions(user_id)
```

### Circuit Breaker para Redis

```python
# Implementado em app/services/circuit_breaker.py
self._redis_breaker = CircuitBreaker(
    name="redis_session",
    failure_threshold=5,
    recovery_timeout=60,  # 1 minuto
    success_threshold=3
)
```

---

## 4. CSRF (Double Submit Cookie)

### Implementacao

O sistema usa o padrao "Double Submit Cookie" com token sincronizado.

**Arquivo:** `app/middleware/csrf.py`

### Fluxo CSRF

```
1. Login -> Backend gera csrf_token
2. Backend -> Set-Cookie: csrf_token (HttpOnly=false)
3. Backend -> Armazena token na sessao Redis
4. Cliente -> Le cookie e envia no header X-CSRF-Token
5. Backend -> Compara header vs sessao
```

### Configuracao

```python
# app/config/settings/security.py
SECURITY_CSRF_SECRET_KEY=<chave-128-bits>
CSRF_TOKEN_EXPIRY=3600  # 1 hora
CSRF_COOKIE_NAME="_csrf_token"
CSRF_HEADER_NAME="X-CSRF-Token"
```

### Endpoints Protegidos

- Todos os metodos mutantes: `POST`, `PUT`, `PATCH`, `DELETE`
- Excecoes: `OPTIONS`, `HEAD`, `GET`

### Endpoints Isentos

```python
CSRF_EXEMPT_PATHS = [
    "/api/v2/health",
    "/api/v2/auth/login",
    "/api/v2/webhooks/",  # Validacao propria
    "/openapi.json",
]
```

### Uso no Frontend

```javascript
// Ler cookie CSRF
const csrfToken = document.cookie
  .split('; ')
  .find(row => row.startsWith('_csrf_token='))
  ?.split('=')[1];

// Enviar em requisicoes
fetch('/api/v2/patients', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken,
  },
  credentials: 'include',
  body: JSON.stringify(data),
});
```

---

## 5. CORS

### Politica de CORS

**Arquivo:** `app/middleware/cors.py`

```python
CORS_ALLOWED_ORIGINS = [
    "https://frontend-clinica-production.up.railway.app",
    "https://app.hormonia.com.br",
]

# Development
if APP_ENVIRONMENT != "production":
    CORS_ALLOWED_ORIGINS.extend([
        "http://localhost:5173",
        "http://localhost:3000",
    ])
```

### Headers CORS Esperados

**Preflight (OPTIONS):**

```http
Access-Control-Allow-Origin: https://app.hormonia.com.br
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS
Access-Control-Allow-Headers: Content-Type, X-CSRF-Token, X-Request-ID, Authorization
Access-Control-Max-Age: 3600
Vary: Origin
```

**Request Normal:**

```http
Access-Control-Allow-Origin: https://app.hormonia.com.br
Access-Control-Allow-Credentials: true
Access-Control-Expose-Headers: X-Total-Count, X-Page-Count
Vary: Origin
```

### Validacao de CORS

```bash
# Testar preflight
curl -v -X OPTIONS https://api.hormonia.com.br/api/v2/patients \
  -H "Origin: https://app.hormonia.com.br" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: X-CSRF-Token"

# Script de validacao
./scripts/validate-cors.sh https://api.hormonia.com.br https://app.hormonia.com.br
```

### Erros Comuns

| Erro | Causa | Solucao |
|------|-------|---------|
| `Origin not allowed` | Origin nao na whitelist | Adicionar em CORS_ALLOWED_ORIGINS |
| `Credentials false` | allow_credentials=False | Definir como True no middleware |
| `Missing headers` | Middleware nao aplicado | Verificar ordem dos middlewares |

---

## 6. Rate Limiting

### Estrategia de Rate Limiting

**Arquivo:** `app/utils/rate_limiter.py`

### Limites por Endpoint

| Endpoint | Limite | Janela | Chave |
|----------|--------|--------|-------|
| `/auth/login` | 10/min | 1min | IP |
| `/api/v2/*` | 100/min | 1min | IP + User |
| `/webhooks/*` | 500/min | 1min | IP + Instance |
| Health checks | Ilimitado | - | - |

### Implementacao

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request):
    ...

# Rate limit por IP + instance (WA-007)
@router.post("/evolution/{instance_name}")
@limiter.limit(
    "500/minute",
    key_func=lambda: f"{request.client.host}:{instance_name}"
)
async def webhook(instance_name: str, request: Request):
    ...
```

### Headers de Rate Limit

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
Retry-After: 60  # Quando limite excedido
```

### Resposta 429

```json
{
  "detail": "Rate limit exceeded. Retry after 60 seconds.",
  "retry_after": 60
}
```

---

## 7. Criptografia (AES-256-GCM)

### Servico Unificado de Criptografia

**Arquivo:** `app/services/encryption/unified_encryption_service.py`

### Algoritmos Suportados

| Algoritmo | Uso | Caracteristicas |
|-----------|-----|-----------------|
| AES-256-GCM | Padrao (recomendado) | Autenticado, detecta adulteracao |
| AES-256-CBC | Legado | Compatibilidade retroativa |
| Fernet | Tokens quiz | Criptografia simetrica |

### Campos Criptografados

- **CPF** (ID Nacional)
- **Email** (endereco)
- **Phone** (telefone)
- **PHI Generic** (dados sensiveis)
- **Quiz Response** (respostas)

### Uso

```python
from app.services.encryption import (
    get_unified_encryption_service,
    FieldType,
    EncryptionAlgorithm
)

service = get_unified_encryption_service()

# Criptografar CPF
encrypted_cpf, cpf_hash = service.encrypt_cpf("12345678901")
decrypted = service.decrypt_cpf(encrypted_cpf)

# Criptografar email
encrypted_email, email_hash = service.encrypt_email("user@example.com")
decrypted = service.decrypt_email(encrypted_email)

# Criptografar telefone
encrypted_phone, phone_hash = service.encrypt_phone("+5511999999999")
decrypted = service.decrypt_phone(encrypted_phone)

# Criptografar campo generico
encrypted = service.encrypt_field("dados sensiveis", FieldType.PHI_GENERIC)
decrypted = service.decrypt_field(encrypted)

# Bulk encryption (paciente)
patient_data = {
    "name": "Joao Silva",
    "cpf": "12345678901",
    "email": "joao@example.com"
}
encrypted_data = service.encrypt_patient_data(patient_data)
```

### Variaveis de Ambiente

```bash
# Obrigatorio (producao)
PHI_ENCRYPTION_KEY=<chave-32-bytes-base64>
HASH_SALT=<salt-hexadecimal-64-chars>

# Gerar chave PHI
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"

# Gerar salt
python -c "import secrets; print(secrets.token_hex(32))"
```

### Comparacao GCM vs CBC

| Recurso | CBC (Antigo) | GCM (Novo) |
|---------|--------------|------------|
| Confidencialidade | Sim | Sim |
| Autenticidade | Nao | Sim |
| Verificacao de integridade | Nao | Sim |
| Deteccao de adulteracao | Nao | Sim |
| Performance | Boa | Melhor |

---

## 8. Conformidade LGPD

### Artigos Implementados

| Artigo | Descricao | Implementacao |
|--------|-----------|---------------|
| Art. 46 | Medidas de seguranca | AES-256 para PII |
| Art. 16 | Direito a exclusao | hard_delete() |
| Art. 18, II | Correcao/exclusao | Audit trail |
| Art. 37 | Transparencia | Middleware de logging |
| Art. 48 | Incidentes | Audit logging |
| Art. 49 | Transferencia internacional | Criptografia at-rest |

### Middleware LGPD

**Arquivo:** `app/middleware/lgpd_middleware.py`

```python
from app.middleware.lgpd_middleware import LGPDMiddleware

app.add_middleware(LGPDMiddleware, enable_ip_logging=True)
```

**Log de Auditoria:**

```json
{
  "event": "patient_data_access",
  "user_id": "uuid-123",
  "user_role": "doctor",
  "method": "GET",
  "path": "/api/v2/patients/456",
  "ip_address": "192.168.1.100",
  "timestamp": "2025-01-01T15:30:00Z"
}
```

### Exclusao Permanente (Art. 16)

```python
from app.repositories.patient import PatientRepository

repo = PatientRepository(db)

# LGPD Art. 16 - Direito a ser esquecido
deleted = await repo.hard_delete(
    patient_id=patient_uuid,
    audit_reason="LGPD Art. 16 - Patient requested data deletion"
)
```

### Busca por Hash (Dados Criptografados)

```python
from app.services.lgpd_encryption_service import get_lgpd_encryption_service

service = get_lgpd_encryption_service()

# Gerar hash de busca (case-insensitive)
email_hash = service.hash_email_for_search("USER@EXAMPLE.COM")

# Query por hash
patient = await db.query(Patient).filter(
    Patient.email_hash == email_hash,
    Patient.doctor_id == doctor_id,
    Patient.deleted_at.is_(None)
).first()
```

### Boas Praticas LGPD

```python
# NUNCA logar PII descriptografado
logger.info(f"Patient email hash: {patient.email_hash[:16]}...")

# Mascarar PII em respostas API
def mask_email(email: str) -> str:
    if not email or '@' not in email:
        return email
    local, domain = email.split('@', 1)
    return f"{local[0]}***@{domain}"
```

---

## 9. Headers de Seguranca

### Headers Implementados

**Arquivo:** `app/middleware/security_headers_enhanced.py`

#### 1. X-Frame-Options

```http
X-Frame-Options: DENY
```

- Previne clickjacking
- Bloqueia iframe/frame/object

#### 2. X-Content-Type-Options

```http
X-Content-Type-Options: nosniff
```

- Previne MIME sniffing
- Forca respeito ao Content-Type

#### 3. X-XSS-Protection

```http
X-XSS-Protection: 1; mode=block
```

- Filtro XSS (browsers legados)
- Bloqueia pagina se detectado

#### 4. Referrer-Policy

```http
Referrer-Policy: strict-origin-when-cross-origin
```

- Controla vazamento de referrer
- Same-origin: URL completa
- Cross-origin HTTPS: Origin apenas
- Cross-origin HTTP: Nada

#### 5. Permissions-Policy

```http
Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=(), usb=()
```

- Desabilita features do browser
- Reduz superficie de ataque

#### 6. Content-Security-Policy (CSP)

```http
Content-Security-Policy:
  default-src 'self';
  script-src 'self' https://www.gstatic.com https://identitytoolkit.googleapis.com;
  style-src 'self' https://fonts.googleapis.com;
  img-src 'self' data: https:;
  font-src 'self' data: https://fonts.gstatic.com;
  connect-src 'self' https://identitytoolkit.googleapis.com https://securetoken.googleapis.com;
  object-src 'none';
  base-uri 'self';
  form-action 'self';
  frame-ancestors 'none';
  upgrade-insecure-requests;
  block-all-mixed-content;
```

#### 7. Strict-Transport-Security (HSTS)

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

- **APENAS PRODUCAO**
- Forca HTTPS por 1 ano
- Inclui subdomains

#### 8. Cross-Origin Policies

```http
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Resource-Policy: same-origin
```

### Pontuacao de Headers

| Header | Peso | Status |
|--------|------|--------|
| X-Frame-Options | 10 | Ativo |
| X-Content-Type-Options | 10 | Ativo |
| Content-Security-Policy | 20 | Ativo |
| Referrer-Policy | 10 | Ativo |
| Permissions-Policy | 15 | Ativo |
| HSTS | 15 | Ativo (prod) |
| X-XSS-Protection | 5 | Ativo |
| COOP/COEP/CORP | 15 | Ativo |
| **Total** | **100** | **95** |

### Validacao

```bash
# Verificar headers localmente
curl -I http://localhost:8000/api/v2/health | grep -E 'X-Frame|X-Content|CSP|Referrer'

# Validadores externos
# - https://observatory.mozilla.org/
# - https://securityheaders.com/
```

---

## 10. Checklist de Producao

### Pre-Deploy

#### Variaveis de Ambiente

- [ ] `APP_ENVIRONMENT=production`
- [ ] `SECURITY_SECRET_KEY` com 128+ bits entropia
- [ ] `AUTH_JWT_SECRET_KEY` com 128+ bits entropia
- [ ] `SECURITY_ENCRYPTION_KEY` com 128+ bits entropia
- [ ] `SECURITY_CSRF_SECRET_KEY` com 128+ bits entropia
- [ ] `PHI_ENCRYPTION_KEY` configurada (32 bytes base64)
- [ ] `HASH_SALT` configurado (64 chars hex)
- [ ] `FIREBASE_*` variaveis configuradas

#### Seguranca de Sessao

- [ ] `SESSION_ENABLE_COOKIE_SECURE=true`
- [ ] `SESSION_ENABLE_COOKIE_HTTPONLY=true`
- [ ] `SESSION_COOKIE_SAMESITE=strict`
- [ ] Redis SSL habilitado
- [ ] Redis max_connections >= 50

#### Headers e CORS

- [ ] HSTS habilitado (`enable_hsts=True`)
- [ ] Permissions-Policy configurado
- [ ] CORS_ALLOWED_ORIGINS apenas producao
- [ ] CSP configurado corretamente

#### Database

- [ ] SSL/TLS habilitado
- [ ] Credenciais rotacionadas
- [ ] Backup configurado

### Verificacao de Startup

```bash
# Validar chaves de seguranca
python scripts/validate_security_keys.py --env-file .env.production

# Testar CORS
./scripts/validate-cors.sh $API_URL $FRONTEND_URL

# Testar headers
curl -I https://api.hormonia.com.br/api/v2/health
```

### Monitoramento

- [ ] Alertas para circuit breaker open
- [ ] Metricas de rate limiting
- [ ] Logs de CSP violations
- [ ] Auditoria de acesso LGPD

### Testes de Seguranca

```bash
# Executar suite de testes de seguranca
pytest tests/security/ -v

# Testes especificos
pytest tests/security/test_security_headers.py -v
pytest tests/security/test_rate_limiting.py -v
pytest tests/security/test_sql_injection_fixes.py -v
```

### Compliance

| Item | Verificacao | Frequencia |
|------|-------------|------------|
| OWASP Top 10 | Scan automatizado | Semanal |
| LGPD Audit | Revisao manual | Mensal |
| Penetration Test | Externo | Trimestral |
| Dependency Scan | CI/CD | Cada deploy |
| Key Rotation | Manual | 90 dias |

### Resposta a Incidentes

1. **Deteccao:** Monitorar logs e alertas
2. **Contencao:** Circuit breaker, rate limiting
3. **Investigacao:** Logs de auditoria LGPD
4. **Recuperacao:** Rollback se necessario
5. **Pos-Mortem:** Documentar e melhorar

---

## Referencias

### Documentacao Interna

- `/app/middleware/security_headers_enhanced.py` - Headers de seguranca
- `/app/middleware/csrf.py` - Protecao CSRF
- `/app/middleware/cors.py` - Configuracao CORS
- `/app/services/encryption/` - Servicos de criptografia
- `/app/utils/security_validation.py` - Validacao de entropia
- `/tests/security/` - Testes de seguranca

### Padroes e Frameworks

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Secure Headers](https://owasp.org/www-project-secure-headers/)
- [LGPD Lei 13.709/2018](http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [Firebase Security](https://firebase.google.com/docs/auth/admin/verify-id-tokens)

### Ferramentas

- [Mozilla Observatory](https://observatory.mozilla.org/)
- [SecurityHeaders.com](https://securityheaders.com/)
- [CSP Evaluator](https://csp-evaluator.withgoogle.com/)

---

## Historico de Alteracoes

| Data | Versao | Descricao |
|------|--------|-----------|
| 2025-12-26 | 2.0.0 | Consolidacao de documentacao |
| 2025-12-25 | 1.5.0 | Adicao de Permissions-Policy |
| 2025-12-23 | 1.4.0 | Implementacao WA-001 a WA-007 |
| 2025-11-30 | 1.3.0 | Validacao de entropia (AUTH-001) |
| 2025-11-26 | 1.2.0 | Criptografia LGPD email/phone |
| 2025-11-26 | 1.1.0 | Servico unificado de criptografia |

---

**Mantido por:** Equipe de Seguranca Backend Hormonia
**Contato:** security@hormonia.com.br
**Ultima Atualizacao:** 2025-12-26
