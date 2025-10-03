# Backend API Reference

## 📋 Base URLs

- **Development**: `http://localhost:8000/api/v1`
- **Production**: `https://api.hormonia.app/api/v1`

## 🔐 Authentication

All endpoints (except public ones) require JWT authentication.

**Header:**
```
Authorization: Bearer <access_token>
```

### Authentication Endpoints

#### POST /auth/login
Login and receive tokens.

**Request:**
```json
{
  "email": "doctor@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAi...",
  "refresh_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "email": "doctor@example.com",
    "name": "Dr. Silva",
    "role": "doctor"
  }
}
```

#### POST /auth/refresh
Refresh access token.

**Request:**
```json
{
  "refresh_token": "eyJ0eXAi..."
}
```

#### POST /auth/logout
Logout and blacklist token.

**Headers:** `Authorization: Bearer <token>`

## 👥 Patients

### GET /patients
List all patients (with filters).

**Query Params:**
- `page`: int (default: 1)
- `per_page`: int (default: 20)
- `search`: string (name, phone, email)
- `status`: active | inactive
- `doctor_id`: uuid

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Maria Silva",
      "phone": "+5511999999999",
      "email": "maria@example.com",
      "birth_date": "1980-05-15",
      "status": "active",
      "assigned_doctor_id": "uuid",
      "created_at": "2025-01-01T10:00:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "per_page": 20,
  "pages": 5
}
```

### POST /patients
Create new patient.

**Request:**
```json
{
  "name": "Maria Silva",
  "phone": "+5511999999999",
  "email": "maria@example.com",
  "birth_date": "1980-05-15",
  "assigned_doctor_id": "uuid"
}
```

### GET /patients/{id}
Get patient details.

### PUT /patients/{id}
Update patient.

### DELETE /patients/{id}
Delete patient (soft delete).

## 💬 Messages (WhatsApp)

### GET /messages
List messages.

**Query Params:**
- `patient_id`: uuid (filter by patient)
- `direction`: inbound | outbound
- `status`: sent | delivered | read | failed
- `date_from`: ISO date
- `date_to`: ISO date

### POST /messages/send
Send WhatsApp message.

**Request:**
```json
{
  "patient_id": "uuid",
  "message": "Hello! How are you feeling today?",
  "type": "text"
}
```

**Response:**
```json
{
  "id": "uuid",
  "status": "sent",
  "message_id": "whatsapp_msg_id",
  "sent_at": "2025-09-29T10:00:00Z"
}
```

### GET /messages/threads
Get conversation threads grouped by patient.

## 🔄 Conversation Flows

### GET /flows
List all conversation flows.

### POST /flows
Create new flow.

**Request:**
```json
{
  "name": "Bem-estar Mensal",
  "description": "Avaliação mensal de bem-estar",
  "type": "bem_estar",
  "steps": [
    {
      "step": 1,
      "message": "Olá! Como você está se sentindo hoje?",
      "type": "question",
      "options": ["Bem", "Regular", "Mal"]
    }
  ]
}
```

### POST /flows/{id}/start
Start flow for a patient.

**Request:**
```json
{
  "patient_id": "uuid"
}
```

### PUT /flows/{id}/pause
Pause active flow.

### PUT /flows/{id}/resume
Resume paused flow.

## 📋 Quiz System

### GET /quiz/templates
List quiz templates.

### POST /quiz/generate-link
Generate secure quiz link for patient.

**Request:**
```json
{
  "patient_id": "uuid",
  "quiz_type": "monthly_wellness",
  "expires_in_days": 7
}
```

**Response:**
```json
{
  "token": "secure_random_token_32_chars",
  "url": "https://hormonia.app/quiz/secure_random_token_32_chars",
  "expires_at": "2025-10-06T10:00:00Z"
}
```

### POST /quiz/public/{token}
Submit quiz response (no auth required).

**Request:**
```json
{
  "responses": [
    {
      "question_id": 1,
      "answer": "Bem"
    },
    {
      "question_id": 2,
      "answer": 8
    }
  ]
}
```

### GET /quiz/analytics
Get quiz completion analytics.

**Query Params:**
- `patient_id`: uuid
- `date_from`: ISO date
- `date_to`: ISO date

## 🤖 AI Services

### POST /ai/insights
Get AI-generated patient insights.

**Request:**
```json
{
  "patient_id": "uuid",
  "timeframe": "week"
}
```

**Response:**
```json
{
  "insights": [
    {
      "type": "sentiment",
      "title": "Improved mood",
      "description": "Patient shows positive sentiment in last 5 messages",
      "confidence": 0.87,
      "priority": "medium"
    }
  ],
  "generated_at": "2025-09-29T10:00:00Z"
}
```

### POST /ai/recommendations
Get treatment recommendations.

### POST /ai/chat
Interactive AI chat.

**Request:**
```json
{
  "message": "What should I ask patient about side effects?",
  "context": {
    "patient_id": "uuid"
  }
}
```

## 📊 Reports

### GET /reports
List reports.

### POST /reports/generate
Generate new report.

**Request:**
```json
{
  "type": "patient_summary",
  "patient_id": "uuid",
  "date_range": {
    "start": "2025-09-01",
    "end": "2025-09-30"
  }
}
```

### GET /reports/{id}/download
Download report PDF.

## 📈 Analytics

### GET /analytics/dashboard
Get dashboard data.

**Response:**
```json
{
  "total_patients": 150,
  "active_flows": 45,
  "messages_today": 230,
  "quiz_completion_rate": 0.78,
  "recent_alerts": [...]
}
```

## 🔧 Health & Monitoring

### GET /health
Application health check.

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "uptime": 86400,
  "database": "connected",
  "redis": "connected",
  "ai_service": "available"
}
```

### GET /api/v1/redis/health
Detailed Redis health.

**Response:**
```json
{
  "status": "healthy",
  "sync_client": "connected",
  "async_client": "connected",
  "memory_usage": "15.2MB",
  "connected_clients": 3
}
```

## 📝 Response Format

### Success Response
```json
{
  "success": true,
  "data": {...}
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid phone number format",
    "details": {...}
  }
}
```

### HTTP Status Codes
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Too Many Requests
- `500` - Internal Server Error

## 🔒 Rate Limits

- **Login**: 5 attempts / 15 minutes
- **General API**: 100 requests / minute
- **File Upload**: 10 requests / hour
- **Quiz Submission**: 20 requests / hour

**Rate Limit Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1696012800
```

## 🔐 Security

- All endpoints use HTTPS in production
- JWT tokens expire after 30 minutes
- Refresh tokens expire after 7 days
- RLS policies enforce data isolation
- Request/response validation with Pydantic

## 📚 More Info

- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json

---

**Sistema Hormonia API** - FastAPI REST API v2.0.0