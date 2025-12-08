# API Examples - Backend Hormonia

**Version:** 2.1.0
**Last Updated:** 2025-11-16
**Base URL:** `https://api.hormonia.example.com` (Production) / `http://localhost:8000` (Development)

## Table of Contents

1. [Authentication](#authentication)
2. [Patient Management](#patient-management)
3. [Quiz System](#quiz-system)
4. [Flow Engine](#flow-engine)
5. [Messages](#messages)
6. [Alerts](#alerts)
7. [Reports](#reports)
8. [Admin Operations](#admin-operations)
9. [Error Handling](#error-handling)
10. [Pagination](#pagination)

---

## Authentication

### 1. Register New User

**Endpoint:** `POST /api/v2/auth/register`

**Request:**
```http
POST /api/v2/auth/register HTTP/1.1
Host: api.hormonia.example.com
Content-Type: application/json

{
  "email": "dr.silva@hospital.com",
  "password": "SecureP@ssw0rd123",
  "full_name": "Dr. João Silva",
  "role": "doctor",
  "crm": "12345-SP",
  "specialty": "Oncologia"
}
```

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "dr.silva@hospital.com",
  "full_name": "Dr. João Silva",
  "role": "doctor",
  "is_active": true,
  "created_at": "2025-01-16T10:30:00Z",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

**Error Response (400 Bad Request):**
```json
{
  "error": "validation_error",
  "message": "Input validation failed",
  "errors": {
    "email": "Email already registered",
    "password": "Password must be at least 8 characters with uppercase, lowercase, number and symbol"
  },
  "timestamp": "2025-01-16T10:30:00Z",
  "path": "/api/v2/auth/register"
}
```

### 2. Login

**Endpoint:** `POST /api/v2/auth/login`

**Request:**
```http
POST /api/v2/auth/login HTTP/1.1
Host: api.hormonia.example.com
Content-Type: application/json

{
  "email": "dr.silva@hospital.com",
  "password": "SecureP@ssw0rd123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJlbWFpbCI6ImRyLnNpbHZhQGhvc3BpdGFsLmNvbSIsInJvbGUiOiJkb2N0b3IiLCJleHAiOjE3Mzc2MzY2MDB9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 86400,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "dr.silva@hospital.com",
    "full_name": "Dr. João Silva",
    "role": "doctor",
    "is_active": true
  }
}
```

**Error Response (401 Unauthorized):**
```json
{
  "error": "authentication_failed",
  "message": "Invalid email or password",
  "timestamp": "2025-01-16T10:30:00Z",
  "path": "/api/v2/auth/login"
}
```

### 3. Refresh Token

**Endpoint:** `POST /api/v2/auth/refresh`

**Request:**
```http
POST /api/v2/auth/refresh HTTP/1.1
Host: api.hormonia.example.com
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

## Patient Management

### 4. Create Patient (Onboarding)

**Endpoint:** `POST /api/v2/patients`

**Request:**
```http
POST /api/v2/patients HTTP/1.1
Host: api.hormonia.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
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

**Error Response (400 Bad Request - CPF Duplicate):**
```json
{
  "error": "duplicate_patient",
  "message": "Patient with CPF 123.456.789-01 already exists",
  "existing_patient_id": "456e7890-e89b-12d3-a456-426614174002",
  "timestamp": "2025-01-16T10:30:00Z",
  "path": "/api/v2/patients"
}
```

**Error Response (400 Bad Request - Validation):**
```json
{
  "error": "validation_error",
  "message": "Input validation failed",
  "errors": {
    "cpf": "Invalid CPF format (must be 11 digits)",
    "birth_date": "Patient must be at least 18 years old",
    "phone": "Invalid phone number format (must start with +55)",
    "email": "Invalid email address format"
  },
  "timestamp": "2025-01-16T10:30:00Z",
  "path": "/api/v2/patients"
}
```

### 5. List Patients (with Pagination)

**Endpoint:** `GET /api/v2/patients`

**Request:**
```http
GET /api/v2/patients?limit=20&cursor=eyJpZCI6IjEyMyIsImNyZWF0ZWRfYXQiOiIyMDI1LTAxLTE2In0&status=active&doctor_id=550e8400-e29b-41d4-a716-446655440000 HTTP/1.1
Host: api.hormonia.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Query Parameters:**
- `limit` (optional): Number of results per page (default: 20, max: 100)
- `cursor` (optional): Pagination cursor from previous response
- `status` (optional): Filter by status (`active`, `inactive`, `archived`)
- `doctor_id` (optional): Filter by doctor
- `search` (optional): Search by name, CPF, or email

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
        "name": "Dr. João Silva"
      },
      "flow_state": {
        "current_step": "monthly_quiz",
        "progress": 45
      }
    },
    {
      "id": "789e4567-e89b-12d3-a456-426614174002",
      "name": "João Pedro Oliveira",
      "cpf": "234.567.890-12",
      "phone": "+55 11 98765-4322",
      "status": "active",
      "cancer_type": "lung",
      "created_at": "2025-01-15T14:20:00Z",
      "doctor": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Dr. João Silva"
      },
      "flow_state": {
        "current_step": "welcome_message",
        "progress": 10
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

### 6. Get Patient Details

**Endpoint:** `GET /api/v2/patients/{patient_id}`

**Request:**
```http
GET /api/v2/patients/789e4567-e89b-12d3-a456-426614174001 HTTP/1.1
Host: api.hormonia.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response (200 OK):**
```json
{
  "id": "789e4567-e89b-12d3-a456-426614174001",
  "name": "Maria Silva Santos",
  "cpf": "123.456.789-01",
  "birth_date": "1985-06-15",
  "age": 39,
  "phone": "+55 11 98765-4321",
  "email": "maria.silva@example.com",
  "status": "active",
  "cancer_type": "breast",
  "diagnosis_date": "2025-01-10",
  "created_at": "2025-01-16T10:30:00Z",
  "updated_at": "2025-01-16T10:30:00Z",
  "doctor": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Dr. João Silva",
    "email": "dr.silva@hospital.com",
    "crm": "12345-SP"
  },
  "metadata": {
    "preferred_contact": "whatsapp",
    "emergency_contact": "+5511999887766",
    "preferred_language": "pt-BR"
  },
  "flow_state": {
    "id": "flow-state-123",
    "status": "active",
    "current_step": "monthly_quiz",
    "progress": 45,
    "started_at": "2025-01-16T10:30:00Z",
    "last_activity": "2025-01-17T15:45:00Z",
    "template": {
      "id": "template-v1",
      "name": "Onboarding Flow V1",
      "version": "1.0.0"
    }
  },
  "statistics": {
    "total_messages": 47,
    "total_quizzes_completed": 3,
    "total_alerts": 2,
    "last_interaction": "2025-01-17T15:45:00Z"
  }
}
```

**Error Response (404 Not Found):**
```json
{
  "error": "patient_not_found",
  "message": "Patient with ID 789e4567-e89b-12d3-a456-426614174001 not found",
  "timestamp": "2025-01-16T10:30:00Z",
  "path": "/api/v2/patients/789e4567-e89b-12d3-a456-426614174001"
}
```

### 7. Update Patient

**Endpoint:** `PATCH /api/v2/patients/{patient_id}`

**Request:**
```http
PATCH /api/v2/patients/789e4567-e89b-12d3-a456-426614174001 HTTP/1.1
Host: api.hormonia.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "phone": "+5511987654399",
  "email": "maria.silva.new@example.com",
  "metadata": {
    "preferred_contact": "email",
    "emergency_contact": "+5511999887799"
  }
}
```

**Response (200 OK):**
```json
{
  "id": "789e4567-e89b-12d3-a456-426614174001",
  "name": "Maria Silva Santos",
  "cpf": "123.456.789-01",
  "phone": "+55 11 98765-4399",
  "email": "maria.silva.new@example.com",
  "status": "active",
  "updated_at": "2025-01-16T11:00:00Z",
  "metadata": {
    "preferred_contact": "email",
    "emergency_contact": "+5511999887799",
    "preferred_language": "pt-BR"
  }
}
```

---

## Quiz System

### 8. Create Quiz Session

**Endpoint:** `POST /api/v2/quiz/sessions`

**Request:**
```http
POST /api/v2/quiz/sessions HTTP/1.1
Host: api.hormonia.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
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
    "text": "Como você está se sentindo hoje?",
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

### 9. Submit Quiz Response

**Endpoint:** `POST /api/v2/quiz/sessions/{session_id}/responses`

**Request:**
```http
POST /api/v2/quiz/sessions/quiz-session-456/responses HTTP/1.1
Host: api.hormonia.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
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
    "text": "Você teve alguma dor nas últimas 24 horas?",
    "type": "boolean",
    "required": true
  }
}
```

### 10. Complete Quiz Session

**Endpoint:** `POST /api/v2/quiz/sessions/{session_id}/complete`

**Request:**
```http
POST /api/v2/quiz/sessions/quiz-session-456/complete HTTP/1.1
Host: api.hormonia.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response (200 OK):**
```json
{
  "session_id": "quiz-session-456",
  "status": "completed",
  "completed_at": "2025-01-16T11:00:00Z",
  "total_responses": 15,
  "completion_rate": 100,
  "duration_seconds": 1800,
  "alerts_generated": [
    {
      "id": "alert-123",
      "type": "symptom_alert",
      "severity": "medium",
      "message": "Paciente relatou dores frequentes",
      "triggered_by": "q5",
      "created_at": "2025-01-16T10:45:00Z"
    }
  ],
  "summary": {
    "overall_wellbeing": "good",
    "pain_level": "moderate",
    "side_effects_reported": ["nausea", "fatigue"],
    "requires_followup": true
  }
}
```

---

## Flow Engine

### 11. Get Flow State

**Endpoint:** `GET /api/v2/flows/patients/{patient_id}/state`

**Request:**
```http
GET /api/v2/flows/patients/789e4567-e89b-12d3-a456-426614174001/state HTTP/1.1
Host: api.hormonia.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
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
    },
    {
      "step": "first_followup",
      "completed_at": "2025-01-17T09:00:00Z",
      "duration_seconds": 600
    }
  ]
}
```

### 12. Trigger Flow Execution

**Endpoint:** `POST /api/v2/flows/execute`

**Request:**
```http
POST /api/v2/flows/execute HTTP/1.1
Host: api.hormonia.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "patient_id": "789e4567-e89b-12d3-a456-426614174001",
  "flow_template_id": "onboarding-v1",
  "initial_step": "welcome_message",
  "context": {
    "trigger": "manual",
    "triggered_by": "doctor_id_123"
  }
}
```

**Response (202 Accepted):**
```json
{
  "execution_id": "flow-exec-789",
  "patient_id": "789e4567-e89b-12d3-a456-426614174001",
  "template_id": "onboarding-v1",
  "status": "running",
  "started_at": "2025-01-16T10:30:00Z",
  "current_step": "welcome_message",
  "message": "Flow execution started successfully",
  "tracking_url": "/api/v2/flows/executions/flow-exec-789"
}
```

---

## Messages

### 13. Send Message to Patient

**Endpoint:** `POST /api/v2/messages`

**Request:**
```http
POST /api/v2/messages HTTP/1.1
Host: api.hormonia.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "patient_id": "789e4567-e89b-12d3-a456-426614174001",
  "content": "Olá Maria! Lembre-se de tomar seus medicamentos às 14h. 💊",
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
  "content": "Olá Maria! Lembre-se de tomar seus medicamentos às 14h. 💊",
  "channel": "whatsapp",
  "priority": "normal",
  "status": "scheduled",
  "scheduled_for": "2025-01-16T14:00:00Z",
  "created_at": "2025-01-16T10:30:00Z",
  "idempotency_key": "msg-789e4567-e89b-12d3-a456-426614174001-1737627600"
}
```

### 14. Get Message History

**Endpoint:** `GET /api/v2/messages/patients/{patient_id}`

**Request:**
```http
GET /api/v2/messages/patients/789e4567-e89b-12d3-a456-426614174001?limit=50&cursor=eyJpZCI6Im1lc3NhZ2UtMTIzIiwiY3JlYXRlZF9hdCI6IjIwMjUtMDEtMTZUMTA6MzA6MDBaIn0 HTTP/1.1
Host: api.hormonia.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "message-456",
      "content": "Olá Maria! Lembre-se de tomar seus medicamentos às 14h. 💊",
      "channel": "whatsapp",
      "direction": "outbound",
      "status": "delivered",
      "sent_at": "2025-01-16T14:00:00Z",
      "delivered_at": "2025-01-16T14:00:15Z",
      "read_at": "2025-01-16T14:05:30Z"
    },
    {
      "id": "message-455",
      "content": "Obrigada pelo lembrete!",
      "channel": "whatsapp",
      "direction": "inbound",
      "status": "received",
      "received_at": "2025-01-16T14:06:00Z"
    }
  ],
  "pagination": {
    "limit": 50,
    "has_next": true,
    "next_cursor": "eyJpZCI6Im1lc3NhZ2UtNDU1IiwiY3JlYXRlZF9hdCI6IjIwMjUtMDEtMTZUMTQ6MDY6MDBaIn0"
  }
}
```

---

## Error Handling

### Error Response Format

All error responses follow this consistent format:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "errors": {
    "field_name": "Field-specific error message"
  },
  "timestamp": "2025-01-16T10:30:00Z",
  "path": "/api/v2/endpoint",
  "request_id": "req-123456"
}
```

### Common Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `validation_error` | Input validation failed |
| 401 | `authentication_failed` | Invalid or missing authentication |
| 403 | `permission_denied` | Insufficient permissions |
| 404 | `not_found` | Resource not found |
| 409 | `conflict` | Resource conflict (duplicate, etc.) |
| 422 | `unprocessable_entity` | Semantic validation failed |
| 429 | `rate_limit_exceeded` | Too many requests |
| 500 | `internal_server_error` | Unexpected server error |
| 503 | `service_unavailable` | Service temporarily unavailable |

---

## Pagination

All list endpoints support cursor-based pagination for efficient data retrieval.

### Pagination Parameters

- `limit`: Number of items per page (default: 20, max: 100)
- `cursor`: Opaque cursor string from previous response

### Example

**Request:**
```http
GET /api/v2/patients?limit=20 HTTP/1.1
```

**Response:**
```json
{
  "data": [...],
  "pagination": {
    "limit": 20,
    "has_next": true,
    "next_cursor": "eyJpZCI6IjEyMyIsImNyZWF0ZWRfYXQiOiIyMDI1LTAxLTE2VDEwOjMwOjAwWiJ9",
    "total_count": 127
  }
}
```

**Next Page:**
```http
GET /api/v2/patients?limit=20&cursor=eyJpZCI6IjEyMyIsImNyZWF0ZWRfYXQiOiIyMDI1LTAxLTE2VDEwOjMwOjAwWiJ9 HTTP/1.1
```

---

**For more examples, see:**
- Postman Collection: `backend-hormonia/postman/Backend_Hormonia_API.postman_collection.json`
- OpenAPI Spec: `backend-hormonia/docs/api/openapi.json`
- Interactive Swagger UI: `http://localhost:8000/docs`
