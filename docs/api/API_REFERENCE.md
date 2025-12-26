# API Reference - Sistema Hormonia

**Base URL:** `https://api.hormonia.com/api/v2`
**Versao:** 2.0
**Autenticacao:** Firebase Token + Session Cookie

---

## Autenticacao

### Obter CSRF Token

```http
GET /auth/csrf-token
```

**Response:**
```json
{
  "csrf_token": "1734695123.a1b2c3..."
}
```

### Login Firebase

```http
POST /auth/firebase/verify
Content-Type: application/json

{
  "id_token": "eyJhbGciOiJSUzI1NiIs..."
}
```

**Response:**
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "role": "doctor",
  "session_id": "uuid"
}
```

### Verificar Sessao

```http
GET /auth/verify-session
Cookie: session_id=uuid
```

### Logout

```http
DELETE /auth/logout
Cookie: session_id=uuid
X-CSRF-Token: token
```

---

## Pacientes

### Listar Pacientes

```http
GET /patients?page=1&limit=20
Cookie: session_id=uuid
```

**Response:**
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "pages": 8
}
```

### Criar Paciente

```http
POST /patients
Cookie: session_id=uuid
X-CSRF-Token: token
Content-Type: application/json

{
  "name": "Joao Silva",
  "cpf": "12345678900",
  "phone": "+5511999999999",
  "email": "joao@email.com"
}
```

### Obter Paciente

```http
GET /patients/{id}
Cookie: session_id=uuid
```

### Atualizar Paciente

```http
PATCH /patients/{id}
Cookie: session_id=uuid
X-CSRF-Token: token
Content-Type: application/json

{
  "name": "Joao Silva Santos"
}
```

### Deletar Paciente (Soft Delete)

```http
DELETE /patients/{id}
Cookie: session_id=uuid
X-CSRF-Token: token
```

---

## Quiz

### Obter Sessao de Quiz

```http
GET /quiz/session/{token}
```

**Response:**
```json
{
  "session_id": "uuid",
  "patient_name": "Joao",
  "questions": [...],
  "status": "pending"
}
```

### Enviar Respostas

```http
POST /quiz/session/{token}/responses
Content-Type: application/json

{
  "responses": [
    {"question_id": 1, "answer": 5},
    {"question_id": 2, "answer": 3}
  ]
}
```

### Gerar Link de Quiz

```http
POST /monthly-quiz/generate-link
Cookie: session_id=uuid
X-CSRF-Token: token
Content-Type: application/json

{
  "patient_id": "uuid"
}
```

---

## Flows

### Status do Flow

```http
GET /flows/patient/{id}
Cookie: session_id=uuid
```

### Pausar Flow

```http
POST /flows/patient/{id}/pause
Cookie: session_id=uuid
X-CSRF-Token: token
```

### Retomar Flow

```http
POST /flows/patient/{id}/resume
Cookie: session_id=uuid
X-CSRF-Token: token
```

---

## Codigos de Erro

| Codigo | Descricao |
|--------|-----------|
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden (CSRF) |
| 404 | Not Found |
| 422 | Validation Error |
| 429 | Rate Limited |
| 500 | Internal Error |

---

## Rate Limits

| Endpoint | Limite |
|----------|--------|
| /auth/login | 10/min |
| /auth/* | 60/min |
| /patients/* | 100/min |
| /ai/* | 10/min |

---

**Ultima Atualizacao:** 2025-12-26
