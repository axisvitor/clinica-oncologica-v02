# Referencia da API - Backend Hormonia

**Versao:** 2.1.0
**Ultima Atualizacao:** 2025-12-26
**Base URL:** `https://api.hormonia.example.com` (Producao) | `http://localhost:8000` (Desenvolvimento)

---

## Indice

1. [Visao Geral](#1-visao-geral)
2. [Autenticacao](#2-autenticacao)
3. [Formato de Requisicoes e Respostas](#3-formato-de-requisicoes-e-respostas)
4. [Tratamento de Erros](#4-tratamento-de-erros)
5. [Paginacao](#5-paginacao)
6. [Versionamento](#6-versionamento)
7. [Rate Limiting](#7-rate-limiting)
8. [Exemplos Praticos](#8-exemplos-praticos)

---

## 1. Visao Geral

### 1.1 Resumo dos Endpoints

A API Hormonia oferece mais de 150 endpoints organizados nas seguintes categorias:

| Categoria | Prefixo | Descricao |
|-----------|---------|-----------|
| **Autenticacao** | `/api/v2/auth` | Login, sessoes, CSRF, gerenciamento de usuarios |
| **Pacientes** | `/api/v2/patients` | CRUD, importacao, fluxos, integridade |
| **Consultas** | `/api/v2/appointments` | Agendamentos e gerenciamento |
| **Tratamentos** | `/api/v2/treatments` | Protocolos de tratamento |
| **Medicamentos** | `/api/v2/medications` | Gerenciamento de medicacoes |
| **Quiz** | `/api/v2/quiz` | Sessoes de questionarios |
| **Analytics** | `/api/v2/analytics` | Metricas e relatorios |
| **Fluxos** | `/api/v2/flows` | Motor de fluxos automatizados |
| **Mensagens** | `/api/v2/messages` | Comunicacao com pacientes |
| **Alertas** | `/api/v2/alerts` | Sistema de alertas |
| **Templates** | `/api/v2/templates` | Templates de fluxos e quizzes |
| **Admin** | `/api/v2/admin` | Operacoes administrativas |
| **Sistema** | `/api/v2/system` | Saude e monitoramento |

### 1.2 Endpoints de Saude

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/health/live` | GET | Liveness probe (K8s/Railway) |
| `/health/ready` | GET | Readiness probe (verifica DB) |
| `/health/metrics` | GET | Metricas de saude |
| `/metrics` | GET | Metricas Prometheus |

### 1.3 Status da API

**Grade: A+ (Production Ready)**

- 53 routers registrados
- 150+ endpoints ativos
- CORS configurado (5 origens)
- Rate limiting com Redis
- CSRF protection ativo

---

## 2. Autenticacao

### 2.1 Firebase Authentication

A API utiliza Firebase Admin SDK para autenticacao. O projeto configurado e `sistema-oncologico-auth`.

#### Headers Obrigatorios

```http
Authorization: Bearer <firebase_id_token>
Content-Type: application/json
```

### 2.2 Fluxo de Autenticacao

#### Login com Firebase Token

```http
POST /api/v2/auth/verify-token
Content-Type: application/json

{
  "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**

```json
{
  "valid": true,
  "session_id": "sess_abc123",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "dr.silva@hospital.com",
    "full_name": "Dr. Joao Silva",
    "role": "doctor",
    "is_active": true
  },
  "message": "Login successful"
}
```

### 2.3 CSRF Protection

A API implementa Double Submit Cookie pattern para protecao CSRF.

#### Obter CSRF Token

```http
GET /api/v2/auth/csrf-token
```

**Response:**

```json
{
  "csrf_token": "abc123def456..."
}
```

#### Usar CSRF Token

Include o token em requisicoes que modificam dados:

```http
POST /api/v2/patients
X-CSRF-Token: abc123def456...
Content-Type: application/json
```

### 2.4 Gerenciamento de Sessoes

#### Listar Sessoes Ativas

```http
GET /api/v2/auth/sessions
Authorization: Bearer <token>
```

**Response:**

```json
{
  "sessions": [
    {
      "session_id": "sess_123",
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2025-01-15T10:30:00Z",
      "expires_at": "2025-01-20T10:30:00Z",
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0...",
      "is_current": true,
      "valid": true
    }
  ]
}
```

### 2.5 Refresh Token

```http
POST /api/v2/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

---

## 3. Formato de Requisicoes e Respostas

### 3.1 Content Types Suportados

- `application/json` (padrao)
- `multipart/form-data` (upload de arquivos)

### 3.2 Headers Comuns

#### Request Headers

| Header | Obrigatorio | Descricao |
|--------|-------------|-----------|
| `Authorization` | Sim* | Bearer token |
| `Content-Type` | Sim | application/json |
| `X-CSRF-Token` | Sim** | Token CSRF para mutacoes |
| `Accept` | Nao | application/json |
| `X-Request-ID` | Nao | ID para rastreamento |

*Exceto endpoints publicos
**Apenas para POST, PUT, PATCH, DELETE

#### Response Headers

| Header | Descricao |
|--------|-----------|
| `X-Total-Count` | Total de itens (listas) |
| `X-Page` | Pagina atual |
| `X-Per-Page` | Itens por pagina |
| `X-CSRF-Token` | Novo token CSRF |
| `X-Frame-Options` | DENY |
| `X-Content-Type-Options` | nosniff |
| `X-XSS-Protection` | 1; mode=block |

### 3.3 Formato de Datas

**IMPORTANTE:** Todas as datas devem usar formato ISO 8601 com timezone:

```
// DateTime (com timezone - RFC3339)
"2025-01-15T10:30:00Z"
"2025-01-15T10:30:00+00:00"

// Date (apenas data)
"2025-01-15"
```

### 3.4 UUIDs

Todos os IDs de recursos sao UUIDs v4:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "patient_id": "789e4567-e89b-12d3-a456-426614174001"
}
```

### 3.5 Estrutura de Resposta Padrao

#### Recurso Unico

```json
{
  "id": "uuid",
  "field1": "value1",
  "field2": "value2",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

#### Lista com Paginacao

```json
{
  "data": [
    { "id": "uuid1", ... },
    { "id": "uuid2", ... }
  ],
  "pagination": {
    "limit": 20,
    "has_next": true,
    "next_cursor": "eyJpZCI6...",
    "total_count": 127
  }
}
```

---

## 4. Tratamento de Erros

### 4.1 Formato de Erro Padrao

Todos os erros seguem esta estrutura:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "status_code": 400,
  "details": {
    "field": "optional field name",
    "additional": "context"
  }
}
```

### 4.2 Codigos de Erro HTTP

#### Erros do Cliente (4xx)

| Status | Codigo | Descricao |
|--------|--------|-----------|
| 400 | `BAD_REQUEST` | Requisicao malformada |
| 400 | `BUSINESS_RULE_VIOLATION` | Violacao de regra de negocio |
| 401 | `UNAUTHORIZED` | Autenticacao necessaria |
| 403 | `FORBIDDEN` | Permissoes insuficientes |
| 404 | `NOT_FOUND` | Recurso nao encontrado |
| 409 | `CONFLICT` | Conflito de recurso |
| 409 | `DUPLICATE_RESOURCE` | Violacao de unicidade |
| 422 | `VALIDATION_ERROR` | Validacao de entrada falhou |
| 429 | `RATE_LIMIT_EXCEEDED` | Muitas requisicoes |

#### Erros do Servidor (5xx)

| Status | Codigo | Descricao |
|--------|--------|-----------|
| 500 | `INTERNAL_ERROR` | Erro inesperado |
| 500 | `DATABASE_ERROR` | Operacao de banco falhou |
| 503 | `SERVICE_UNAVAILABLE` | Servico indisponivel |
| 503 | `EXTERNAL_SERVICE_ERROR` | API externa falhou |

### 4.3 Exemplos de Erros

#### Erro de Validacao (422)

```json
{
  "error": "VALIDATION_ERROR",
  "message": "Input validation failed",
  "status_code": 422,
  "details": {
    "errors": {
      "birth_date": "Patient must be at least 18 years old",
      "cpf": "Invalid CPF format"
    }
  }
}
```

#### Recurso Nao Encontrado (404)

```json
{
  "error": "NOT_FOUND",
  "message": "Patient not found",
  "status_code": 404,
  "details": {
    "resource": "Patient",
    "identifier": "123e4567-e89b-12d3-a456-426614174000"
  }
}
```

#### Rate Limit Excedido (429)

```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Too many login attempts. Please try again in 60 seconds.",
  "status_code": 429,
  "details": {
    "retry_after": 60
  }
}
```

#### Conflito - Duplicidade (409)

```json
{
  "error": "DUPLICATE_RESOURCE",
  "message": "Resource already exists",
  "status_code": 409,
  "details": {
    "field": "cpf"
  }
}
```

### 4.4 Constraints de Banco Mapeadas

| Constraint | Campo |
|------------|-------|
| `uq_patient_cpf_doctor` | cpf |
| `uq_patient_email_doctor` | email |
| `uq_patient_phone_doctor` | phone |

---

## 5. Paginacao

### 5.1 Cursor-Based Pagination

A API utiliza paginacao baseada em cursor para performance otima em grandes datasets.

**Vantagens:**
- O(1) complexidade independente da pagina
- 150x mais rapido que offset em paginas profundas
- Consistencia durante iteracao

### 5.2 Parametros de Query

| Parametro | Tipo | Descricao | Padrao | Max |
|-----------|------|-----------|--------|-----|
| `cursor` | string | Cursor da resposta anterior | null | - |
| `limit` | integer | Itens por pagina | 50 | 100 |
| `fields` | string | Campos a incluir (CSV) | all | - |
| `include` | string | Relacionamentos (CSV) | none | - |

### 5.3 Exemplo de Uso

#### Primeira Requisicao

```http
GET /api/v2/patients?limit=50
Authorization: Bearer <token>
```

**Response:**

```json
{
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Maria Silva",
      "email": "maria@example.com",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "next_cursor": "eyJpZCI6IjEyM2U0NTY3LWU4OWItMTJkMy1hNDU2LTQyNjYxNDE3NDAwMCIsImNyZWF0ZWRfYXQiOiIyMDI1LTAxLTE1VDEwOjMwOjAwWiJ9",
  "has_next": true,
  "has_prev": false,
  "total_count": null
}
```

#### Proxima Pagina

```http
GET /api/v2/patients?limit=50&cursor=eyJpZCI6IjEyM2U0NTY3...
```

### 5.4 Selecao de Campos

Reduza o tamanho da resposta selecionando campos:

```http
GET /api/v2/patients?limit=50&fields=id,name,email
```

### 5.5 Carregamento de Relacionamentos

```http
GET /api/v2/patients?limit=50&include=doctor,quiz_sessions
```

**Response com relacionamentos:**

```json
{
  "data": [
    {
      "id": "123e4567...",
      "name": "Maria Silva",
      "doctor": {
        "id": "456...",
        "name": "Dr. Silva"
      },
      "quiz_sessions": [
        {
          "id": "789...",
          "status": "completed",
          "score": 85.5
        }
      ]
    }
  ]
}
```

### 5.6 Implementacao no Cliente

#### JavaScript/TypeScript

```typescript
interface PaginatedResponse<T> {
  data: T[];
  next_cursor: string | null;
  has_next: boolean;
  has_prev: boolean;
  total_count: number | null;
}

async function fetchAllPatients(): Promise<Patient[]> {
  let cursor: string | null = null;
  const allPatients: Patient[] = [];

  do {
    const url = cursor
      ? `/api/v2/patients?limit=50&cursor=${encodeURIComponent(cursor)}`
      : `/api/v2/patients?limit=50`;

    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const page: PaginatedResponse<Patient> = await response.json();

    allPatients.push(...page.data);
    cursor = page.next_cursor;

  } while (cursor !== null);

  return allPatients;
}
```

#### Python

```python
import requests
from typing import Iterator, Optional

def iterate_patients(base_url: str, token: str, limit: int = 50) -> Iterator[dict]:
    """Iterate through all patients using cursor pagination."""
    cursor: Optional[str] = None

    while True:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        response = requests.get(
            f"{base_url}/api/v2/patients",
            params=params,
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        data = response.json()

        for patient in data["data"]:
            yield patient

        if not data.get("has_next", False):
            break
        cursor = data.get("next_cursor")
```

---

## 6. Versionamento

### 6.1 Estrategia de Versionamento

A API usa versionamento baseado em URL:

- **v2**: Versao atual (em deprecacao)
- **v3**: Nova versao (recomendada)

```
https://api.hormonia.example.com/api/v2/patients  # Deprecated
https://api.hormonia.example.com/api/v3/patients  # Recommended
```

### 6.2 Timeline de Deprecacao

| Fase | Periodo | Status |
|------|---------|--------|
| **Announce** | Jan - Mar 2025 | v3 disponivel, v2 deprecated |
| **Warn** | Apr - Jun 2025 | Emails semanais, tracking |
| **Sunset** | Jul 1, 2025 | v2 removido (410 Gone) |

### 6.3 Headers de Deprecacao (RFC 8594)

Respostas da v2 incluem headers de deprecacao:

```http
Deprecation: true
Sunset: Tue, 01 Jul 2025 00:00:00 GMT
Link: </api/v3/patients>; rel="successor-version"
```

### 6.4 Diferencas entre v2 e v3

#### Formato de Erro

**v2:**
```json
{
  "error": "Patient not found"
}
```

**v3:**
```json
{
  "error": {
    "code": "PATIENT_NOT_FOUND",
    "message": "Patient not found",
    "field": "patient_id"
  }
}
```

#### Paginacao

**v2 (offset-based):**
```http
GET /api/v2/patients?page=10&limit=50
```

**v3 (cursor-based):**
```http
GET /api/v3/patients?cursor=abc123&limit=50
```

#### Nomes de Campos

| v2 | v3 |
|----|-----|
| `telefone` | `phone` |
| `data_nascimento` | `date_of_birth` |
| `endereco` | `address` |
| `nome` | `name` |

#### Formatacao de CPF

**v2:** `12345678901`
**v3:** `123.456.789-01`

### 6.5 Guia de Migracao v2 para v3

#### Passo 1: Atualizar Base URL

```javascript
// v2
const BASE_URL = 'https://api.hormonia.example.com/api/v2';

// v3
const BASE_URL = 'https://api.hormonia.example.com/api/v3';
```

#### Passo 2: Atualizar Tratamento de Erros

```javascript
// v2
if (response.error) {
  console.error(response.error);
}

// v3
if (response.error) {
  console.error(`[${response.error.code}] ${response.error.message}`);
  if (response.error.field) {
    console.error(`Field: ${response.error.field}`);
  }
}
```

#### Passo 3: Atualizar Paginacao

```javascript
// v2
async function fetchPage(pageNumber, pageSize) {
  const offset = (pageNumber - 1) * pageSize;
  return fetch(`/api/v2/patients?limit=${pageSize}&offset=${offset}`);
}

// v3
async function fetchPage(cursor, pageSize) {
  const url = cursor
    ? `/api/v3/patients?limit=${pageSize}&cursor=${encodeURIComponent(cursor)}`
    : `/api/v3/patients?limit=${pageSize}`;

  const response = await fetch(url);
  const data = await response.json();

  return {
    items: data.data,
    nextCursor: data.pagination.next_cursor,
    hasMore: data.pagination.has_more
  };
}
```

---

## 7. Rate Limiting

### 7.1 Limites Configurados

| Tipo | Limite | Janela |
|------|--------|--------|
| **Global** | 60 requisicoes | 1 minuto |
| **Auth** | 10 requisicoes | 1 minuto |

### 7.2 Headers de Rate Limit

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642348800
```

### 7.3 Resposta de Rate Limit Excedido

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
Content-Type: application/json

{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests. Please try again in 60 seconds.",
  "status_code": 429,
  "details": {
    "retry_after": 60
  }
}
```

### 7.4 Melhores Praticas

1. **Implemente backoff exponencial**
2. **Cache respostas quando possivel**
3. **Use batch operations** quando disponiveis
4. **Monitore headers** de rate limit

```javascript
async function fetchWithRateLimit(url, options) {
  const response = await fetch(url, options);

  if (response.status === 429) {
    const retryAfter = response.headers.get('Retry-After') || 60;
    await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
    return fetchWithRateLimit(url, options);
  }

  return response;
}
```

---

## 8. Exemplos Praticos

### 8.1 Criar Paciente (Onboarding)

```http
POST /api/v2/patients
Authorization: Bearer <token>
X-CSRF-Token: <csrf_token>
Content-Type: application/json

{
  "name": "Maria Silva Santos",
  "cpf": "12345678901",
  "birth_date": "1985-06-15",
  "phone": "+5511987654321",
  "email": "maria.silva@example.com",
  "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
  "cancer_type": "breast",
  "diagnosis_date": "2025-01-10",
  "metadata": {
    "preferred_contact": "whatsapp",
    "emergency_contact": "+5511999887766",
    "preferred_language": "pt-BR"
  }
}
```

**Response (201 Created):**

```json
{
  "id": "789e4567-e89b-12d3-a456-426614174001",
  "name": "Maria Silva Santos",
  "cpf": "123.456.789-01",
  "birth_date": "1985-06-15",
  "phone": "+55 11 98765-4321",
  "email": "maria.silva@example.com",
  "status": "active",
  "cancer_type": "breast",
  "diagnosis_date": "2025-01-10",
  "created_at": "2025-01-16T10:30:00Z",
  "updated_at": "2025-01-16T10:30:00Z",
  "flow_state": {
    "id": "flow-state-123",
    "status": "active",
    "current_step": "welcome_message",
    "progress": 0,
    "started_at": "2025-01-16T10:30:00Z"
  },
  "onboarding_saga": {
    "saga_id": "saga-789",
    "status": "in_progress",
    "steps": [
      {
        "name": "create_patient",
        "status": "completed",
        "completed_at": "2025-01-16T10:30:01Z"
      },
      {
        "name": "initialize_flow",
        "status": "in_progress",
        "started_at": "2025-01-16T10:30:01Z"
      },
      {
        "name": "send_welcome_message",
        "status": "pending"
      }
    ]
  }
}
```

### 8.2 Listar Pacientes com Filtros

```http
GET /api/v2/patients?limit=20&status=active&doctor_id=550e8400-e29b-41d4-a716-446655440000&include=doctor,quiz_sessions
Authorization: Bearer <token>
```

**Response (200 OK):**

```json
{
  "data": [
    {
      "id": "789e4567-e89b-12d3-a456-426614174001",
      "name": "Maria Silva Santos",
      "cpf": "123.456.789-01",
      "phone": "+55 11 98765-4321",
      "email": "maria.silva@example.com",
      "status": "active",
      "cancer_type": "breast",
      "created_at": "2025-01-16T10:30:00Z",
      "doctor": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Dr. Joao Silva"
      },
      "flow_state": {
        "current_step": "monthly_quiz",
        "progress": 45
      }
    }
  ],
  "pagination": {
    "limit": 20,
    "has_next": true,
    "next_cursor": "eyJpZCI6Ijc4OWU0NTY3LWU4OWItMTJkMy1hNDU2LTQyNjYxNDE3NDAwMiIsImNyZWF0ZWRfYXQiOiIyMDI1LTAxLTE1VDE0OjIwOjAwWiJ9",
    "total_count": 127
  }
}
```

### 8.3 Criar Sessao de Quiz

```http
POST /api/v2/quiz/sessions
Authorization: Bearer <token>
X-CSRF-Token: <csrf_token>
Content-Type: application/json

{
  "patient_id": "789e4567-e89b-12d3-a456-426614174001",
  "quiz_template_id": "monthly-symptom-check-v1",
  "delivery_method": "whatsapp"
}
```

**Response (201 Created):**

```json
{
  "session_id": "quiz-session-456",
  "patient_id": "789e4567-e89b-12d3-a456-426614174001",
  "quiz_template_id": "monthly-symptom-check-v1",
  "status": "active",
  "current_question_index": 0,
  "total_questions": 15,
  "progress": 0,
  "created_at": "2025-01-16T10:30:00Z",
  "expires_at": "2025-01-18T10:30:00Z",
  "delivery_method": "whatsapp",
  "quiz_url": "https://quiz.hormonia.example.com/session/quiz-session-456?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "first_question": {
    "id": "q1",
    "text": "Como voce esta se sentindo hoje?",
    "type": "multiple_choice",
    "options": [
      {"value": "very_good", "label": "Muito bem"},
      {"value": "good", "label": "Bem"},
      {"value": "neutral", "label": "Normal"},
      {"value": "bad", "label": "Mal"},
      {"value": "very_bad", "label": "Muito mal"}
    ],
    "required": true
  }
}
```

### 8.4 Submeter Resposta de Quiz

```http
POST /api/v2/quiz/sessions/quiz-session-456/responses
Authorization: Bearer <token>
X-CSRF-Token: <csrf_token>
Content-Type: application/json

{
  "question_id": "q1",
  "response_value": {
    "selected": "good",
    "text": "Me sentindo bem hoje, sem dores"
  }
}
```

**Response (200 OK):**

```json
{
  "response_id": "response-789",
  "session_id": "quiz-session-456",
  "question_id": "q1",
  "response_value": {
    "selected": "good",
    "text": "Me sentindo bem hoje, sem dores"
  },
  "answered_at": "2025-01-16T10:35:00Z",
  "session_progress": {
    "current_question_index": 1,
    "total_questions": 15,
    "progress": 6.67,
    "is_complete": false
  },
  "next_question": {
    "id": "q2",
    "text": "Voce teve alguma dor nas ultimas 24 horas?",
    "type": "boolean",
    "required": true
  }
}
```

### 8.5 Enviar Mensagem para Paciente

```http
POST /api/v2/messages
Authorization: Bearer <token>
X-CSRF-Token: <csrf_token>
Content-Type: application/json

{
  "patient_id": "789e4567-e89b-12d3-a456-426614174001",
  "content": "Ola Maria! Lembre-se de tomar seus medicamentos as 14h.",
  "channel": "whatsapp",
  "priority": "normal",
  "scheduled_for": "2025-01-16T14:00:00Z"
}
```

**Response (201 Created):**

```json
{
  "id": "message-456",
  "patient_id": "789e4567-e89b-12d3-a456-426614174001",
  "content": "Ola Maria! Lembre-se de tomar seus medicamentos as 14h.",
  "channel": "whatsapp",
  "priority": "normal",
  "status": "scheduled",
  "scheduled_for": "2025-01-16T14:00:00Z",
  "created_at": "2025-01-16T10:30:00Z",
  "idempotency_key": "msg-789e4567-e89b-12d3-a456-426614174001-1737627600"
}
```

### 8.6 Obter Estado do Fluxo

```http
GET /api/v2/flows/patients/789e4567-e89b-12d3-a456-426614174001/state
Authorization: Bearer <token>
```

**Response (200 OK):**

```json
{
  "id": "flow-state-123",
  "patient_id": "789e4567-e89b-12d3-a456-426614174001",
  "template_id": "onboarding-v1",
  "template_version": "1.0.0",
  "status": "active",
  "current_step": "monthly_quiz",
  "step_index": 3,
  "total_steps": 8,
  "progress": 37.5,
  "started_at": "2025-01-16T10:30:00Z",
  "last_activity": "2025-01-17T15:45:00Z",
  "state_data": {
    "welcome_message_sent": true,
    "first_quiz_completed": true,
    "monthly_quiz_count": 1,
    "alerts_generated": 2
  },
  "history": [
    {
      "step": "welcome_message",
      "completed_at": "2025-01-16T10:35:00Z",
      "duration_seconds": 300
    },
    {
      "step": "initial_quiz",
      "completed_at": "2025-01-16T12:00:00Z",
      "duration_seconds": 1800
    }
  ]
}
```

---

## Referencias Adicionais

### Documentacao Interativa

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI Schema:** `http://localhost:8000/openapi.json`

### Arquivos de Referencia

| Arquivo | Localizacao |
|---------|-------------|
| Exception Classes | `app/core/exceptions.py` |
| Middleware | `app/middleware/exception_handler.py` |
| Versioning | `app/api/versioning.py` |
| Schemas V2 | `app/schemas/v2/` |
| Routers V2 | `app/api/v2/routers/` |

### Suporte

- **Email:** api-support@hormonia.com
- **Documentacao:** https://docs.hormonia.com
- **Status Page:** https://status.hormonia.com

---

**Documento gerado em:** 2025-12-26
**Versao da API:** 2.1.0
**Status:** Production Ready
