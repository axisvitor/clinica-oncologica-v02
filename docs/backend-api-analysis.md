# Backend API Analysis - Frontend-Backend Connectivity

**Analysis Date**: 2025-10-04
**Analyzed By**: Backend Developer Agent
**Status**: ✅ Complete

---

## Executive Summary

The backend API is well-configured with comprehensive CORS support, WebSocket endpoints, and a public `/api/config` endpoint for frontend runtime configuration. The system uses Firebase Authentication with a custom PatternCORSMiddleware that supports wildcard Railway deployment URLs.

---

## 1. API Endpoints Inventory

### 1.1 Core Authentication & User Management
- `POST /api/v1/auth/login` - User login with Firebase token
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/refresh` - Token refresh
- `GET /api/v1/auth/me` - Current user profile
- All auth endpoints require Firebase JWT token validation

### 1.2 Configuration Endpoint (PUBLIC)
- `GET /api/v1/config` - **PRIMARY** public config endpoint
- `GET /config` - **ALIAS** for frontend compatibility
- `OPTIONS /api/v1/config` - CORS preflight handler
- **Authentication**: ❌ None required (PUBLIC)
- **Purpose**: Provides frontend runtime configuration including:
  - `VITE_API_BASE_URL`: Base API URL for REST calls
  - `VITE_WS_BASE_URL`: WebSocket connection URL
  - `VITE_API_URL`: Main backend URL
  - Firebase public configuration (if available)
  - Feature flags
  - Environment settings
  - CORS allowed origins list

### 1.3 WebSocket Endpoints
- `WS /ws/connect` - Main WebSocket endpoint for real-time communication
  - Query param: `token` (optional JWT for immediate auth)
  - Message types: `authenticate`, `join_room`, `leave_room`, `ping`, `pong`
  - Events: `connected`, `authenticated`, `patient_updated`, `error`, `pong`

- `WS /ws/patient/{patient_id}` - Patient-specific WebSocket
  - Requires authentication via `token` query parameter
  - Auto-joins patient room on connection
  - Dedicated for healthcare provider monitoring

- `WS /ws/enhanced/*` - Enhanced WebSocket features
  - Advanced real-time capabilities

### 1.4 Patient Management
- `GET /api/v1/patients` - List patients
- `POST /api/v1/patients` - Create patient
- `GET /api/v1/patients/{id}` - Get patient details
- `PUT /api/v1/patients/{id}` - Update patient
- `DELETE /api/v1/patients/{id}` - Delete patient

### 1.5 Messages & Communication
- `POST /api/v1/messages` - Send message
- `GET /api/v1/messages/{patient_id}` - Get patient messages
- `POST /api/v1/enhanced/messages/send-batch` - Batch send messages
- `GET /api/v1/enhanced/messages/analytics` - Message analytics

### 1.6 Quiz & Assessments
- `GET /api/v1/quiz/{patient_id}` - Get quiz for patient
- `POST /api/v1/quiz/{patient_id}/answer` - Submit quiz answer
- `GET /api/v1/monthly-quiz` - Get monthly quiz
- `POST /api/v1/monthly-quiz-public/submit` - **PUBLIC** monthly quiz submission (NO AUTH)

### 1.7 Analytics & Reports
- `GET /api/v1/analytics/dashboard` - Dashboard analytics
- `GET /api/v1/reports/{patient_id}` - Generate patient report
- `GET /api/v1/enhanced/analytics/engagement-trends` - Engagement analytics
- `GET /api/v1/enhanced/analytics/patient-insights/{patient_id}` - Patient insights

### 1.8 Health & Monitoring
- `GET /api/v1/health` - Basic health check
- `GET /api/v1/health/detailed` - Detailed system health
- `GET /api/v1/health/readiness` - Kubernetes readiness probe
- `GET /api/v1/health/liveness` - Kubernetes liveness probe
- `GET /api/v1/redis/health` - Redis connection health
- `GET /api/v1/database/health` - Database health status
- `GET /` - Railway health check endpoint

### 1.9 Admin Endpoints (Require Admin Role)
- `POST /api/v1/admin/users` - Create admin user
- `GET /api/v1/admin/users` - List all users
- `PUT /api/v1/admin/users/{user_id}` - Update user
- `POST /api/v1/admin/roles/users/{user_id}/role` - Assign role
- `GET /api/v1/admin/roles/statistics` - Role distribution stats

### 1.10 AI & Automation
- `POST /api/v1/ai/humanize-message` - Humanize AI-generated messages
- `POST /api/v1/ai/analyze-conversation` - Analyze conversation patterns
- `POST /api/v1/ai/generate-insights` - Generate patient insights
- `GET /api/v1/ai/health-metrics/{patient_id}` - AI health metrics

---

## 2. CORS Configuration Analysis

### 2.1 Middleware: PatternCORSMiddleware
**Location**: `backend-hormonia/app/middleware/custom_cors.py`

**Key Features**:
- ✅ Wildcard pattern support for Railway deployments
- ✅ Regex-based origin matching
- ✅ WebSocket header support
- ✅ Proper CORS preflight handling

### 2.2 Allowed Origins (from .env)
```json
[
  "https://frontend-production-18bb.up.railway.app",
  "https://quiz-interface-production.up.railway.app",
  "https://hormonia-frontend.railway.app",
  "https://quiz-mensal-interface.railway.app"
]
```

### 2.3 Pattern Support
The middleware automatically converts wildcard patterns:
- `https://*.railway.app` → Matches any Railway subdomain
- `https://quiz-*.railway.app` → Matches quiz with any prefix
- `https://*-quiz.railway.app` → Matches any prefix with quiz suffix

### 2.4 Allowed Headers
```javascript
[
  "Accept", "Accept-Language", "Content-Language", "Content-Type",
  "Authorization", "X-Requested-With", "X-Request-ID", "X-Correlation-ID",
  // Quiz-specific
  "X-Quiz-Token", "X-Patient-ID", "X-Monthly-Quiz-Token", "X-Session-ID",
  // WebSocket
  "Sec-WebSocket-Protocol", "Sec-WebSocket-Extensions",
  "Sec-WebSocket-Key", "Sec-WebSocket-Version", "Upgrade", "Connection"
]
```

### 2.5 Exposed Headers
```javascript
[
  "X-Request-ID", "X-Correlation-ID", "X-Process-Time",
  "X-Quiz-Session-ID", "X-Quiz-Progress",
  "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset",
  "X-Query-Count", "X-DB-Time-Ms", "X-Request-Duration"
]
```

### 2.6 CORS Settings
- **Credentials**: ✅ Enabled (`allow_credentials: true`)
- **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`
- **Max Age**: 86400 seconds (24 hours)

---

## 3. WebSocket Configuration

### 3.1 Main WebSocket Endpoint
**URL Format**:
- Development: `ws://localhost:8000/ws/connect`
- Production: `wss://{BACKEND_URL}/ws/connect`

**Connection Flow**:
1. Client connects to `/ws/connect`
2. Server accepts connection immediately (no pre-auth required)
3. Server sends `CONNECTED` event with `connection_id`
4. Client can authenticate via:
   - Query parameter: `?token={JWT}`
   - Message: `{type: "authenticate", data: {token: "..."}}`
5. After auth, client joins rooms via `join_room` message

**Supported Message Types**:
```javascript
// Inbound (Client → Server)
{type: "authenticate", data: {token: "..."}}
{type: "join_room", data: {patient_id: "..."}}
{type: "leave_room", data: {patient_id: "..."}}
{type: "ping"}
{type: "pong"}

// Outbound (Server → Client)
{type: "connected", data: {connection_id: "...", authenticated: false}}
{type: "authenticated", data: {success: true, user_id: "...", user_role: "..."}}
{type: "patient_updated", data: {...}}
{type: "pong", data: {message: "pong"}}
{type: "error", data: {error: "...", message: "...", details: {}}}
```

### 3.2 WebSocket Security
- ✅ JWT authentication support (optional immediate, required for sensitive operations)
- ✅ Room-based access control (patient rooms)
- ✅ Connection metadata tracking
- ✅ Health monitoring via ping/pong
- ✅ Automatic cleanup on disconnect

### 3.3 WebSocket CORS Headers
The PatternCORSMiddleware includes WebSocket-specific headers:
- `Sec-WebSocket-Protocol`
- `Sec-WebSocket-Extensions`
- `Sec-WebSocket-Key`
- `Sec-WebSocket-Version`
- `Upgrade`
- `Connection`

---

## 4. Authentication System

### 4.1 Firebase Authentication
**Primary Method**: Firebase JWT token validation

**Environment Variables**:
```bash
# Backend Admin SDK (Server-only, PRIVATE)
FIREBASE_ADMIN_PROJECT_ID="sistema-oncologico-auth"
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----..."
FIREBASE_ADMIN_CLIENT_EMAIL="firebase-adminsdk-...@iam.gserviceaccount.com"

# Frontend Web Config (PUBLIC, shared via /api/config)
FIREBASE_WEB_API_KEY="AIzaSy...HDI"
FIREBASE_WEB_PROJECT_ID="sistema-oncologico-auth"
FIREBASE_WEB_APP_ID="1:608742835827:web:..."
FIREBASE_AUTH_DOMAIN="sistema-oncologico-auth.firebaseapp.com"
```

### 4.2 Authentication Flow
1. Frontend authenticates user with Firebase (client-side)
2. Frontend receives Firebase ID token
3. Frontend includes token in requests:
   - Header: `Authorization: Bearer {token}`
   - WebSocket: Query param `?token={token}` or message
4. Backend validates token using Firebase Admin SDK
5. Backend extracts user claims and permissions
6. Backend authorizes request based on role

### 4.3 Public Endpoints (No Auth Required)
- `GET /api/v1/config` - Runtime configuration
- `GET /config` - Config alias
- `OPTIONS /api/v1/config` - CORS preflight
- `POST /api/v1/monthly-quiz-public/submit` - Public quiz submission
- `GET /api/v1/health` - Health checks
- `GET /` - Railway health check

---

## 5. Environment Variables Analysis

### 5.1 Critical Configuration Mismatches
**Status**: ✅ No critical mismatches found

### 5.2 Frontend URLs (from .env)
```bash
FRONTEND_API_URL="https://clinica-oncologica-v02-production.up.railway.app"
FRONTEND_URL="https://frontend-production-18bb.up.railway.app"
QUIZ_URL="https://quiz-interface-production.up.railway.app"
```

### 5.3 CORS Origins Match
✅ All frontend URLs are included in `ALLOWED_ORIGINS`

### 5.4 API URL Configuration
The `/api/config` endpoint dynamically builds URLs based on environment:

**Priority Order**:
1. `FRONTEND_API_URL` (explicit override)
2. Railway environment variables (`RAILWAY_PUBLIC_DOMAIN`, `RAILWAY_STATIC_URL`)
3. Environment-based fallback (production vs development)

**Generated URLs**:
```javascript
{
  "VITE_API_URL": "https://clinica-oncologica-v02-production.up.railway.app",
  "VITE_API_BASE_URL": "https://clinica-oncologica-v02-production.up.railway.app/api/v1",
  "VITE_WS_BASE_URL": "wss://clinica-oncologica-v02-production.up.railway.app/ws"
}
```

---

## 6. Response Formats & Status Codes

### 6.1 Success Response Format
```javascript
{
  "data": {...},
  "timestamp": "2025-10-04T03:00:00.000Z",
  "request_id": "req_..."
}
```

### 6.2 Error Response Format
```javascript
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {...},
  "timestamp": "2025-10-04T03:00:00.000Z",
  "request_id": "req_..."
}
```

### 6.3 Standard Status Codes
- `200 OK` - Successful GET, PUT
- `201 Created` - Successful POST (resource created)
- `204 No Content` - Successful DELETE
- `400 Bad Request` - Validation error
- `401 Unauthorized` - Authentication required or failed
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict (e.g., duplicate)
- `422 Unprocessable Entity` - Semantic validation error
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service temporarily unavailable

---

## 7. Rate Limiting

### 7.1 Configuration
**Middleware**: `EnhancedRateLimitMiddleware`
- Default limit: 200 requests per 60 seconds
- Per-endpoint customization available
- IP-based whitelisting/blacklisting

### 7.2 Rate Limit Headers
```javascript
{
  "X-RateLimit-Limit": "200",
  "X-RateLimit-Remaining": "185",
  "X-RateLimit-Reset": "1633024800"
}
```

---

## 8. Security Features

### 8.1 Middleware Stack (Execution Order)
1. **PatternCORSMiddleware** - CORS validation (first executed)
2. **EnhancedCompressionMiddleware** - Response compression
3. **EnhancedRateLimitMiddleware** - Rate limiting
4. **EnhancedSecurityMiddleware** - Security headers
5. **RequestLoggingMiddleware** - Request logging (debug only)
6. **QueryPerformanceMiddleware** - Database monitoring
7. **MonitoringMiddleware** - APM instrumentation

### 8.2 Security Headers
```javascript
{
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "X-XSS-Protection": "1; mode=block",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
}
```

### 8.3 HTTPS Configuration
```bash
SECURE_SSL_REDIRECT="true"
SESSION_COOKIE_SECURE="true"
SESSION_COOKIE_HTTPONLY="true"
```

---

## 9. Potential Issues & Recommendations

### 9.1 ✅ No Critical Issues Found

### 9.2 Recommendations
1. **WebSocket Reconnection**: Frontend should implement automatic reconnection with exponential backoff
2. **Config Endpoint Caching**: Frontend should cache `/api/config` response (5-minute TTL as per backend)
3. **Error Handling**: Implement consistent error handling for 401, 403, 429, 500 status codes
4. **Request ID Propagation**: Frontend should include `X-Request-ID` header for request tracing
5. **WebSocket Health**: Implement ping/pong heartbeat (recommended interval: 30 seconds)
6. **Token Refresh**: Implement automatic token refresh before expiration (Firebase token expires in 1 hour)

### 9.3 Future Enhancements
1. Consider implementing GraphQL endpoint for complex queries
2. Add API versioning strategy (currently v1)
3. Implement request/response compression for large payloads
4. Add OpenAPI/Swagger UI for API documentation (currently disabled in production)

---

## 10. API Documentation

### 10.1 OpenAPI/Swagger
- **Development**: Available at `/docs` (Swagger UI) and `/redoc` (ReDoc)
- **Production**: Disabled for security (set `DEBUG=true` to enable)
- **Spec**: Available at `/openapi.json` (when enabled)

### 10.2 Security Schemes
```javascript
{
  "BearerAuth": {
    "type": "http",
    "scheme": "bearer",
    "bearerFormat": "JWT"
  },
  "ApiKeyAuth": {
    "type": "apiKey",
    "in": "header",
    "name": "X-API-Key"
  }
}
```

---

## 11. Performance Metrics

### 11.1 Query Performance Headers
Backend exposes performance metrics via custom headers:
```javascript
{
  "X-Query-Count": "3",          // Number of database queries
  "X-DB-Time-Ms": "45",          // Total database time in milliseconds
  "X-Request-Duration": "125"    // Total request duration in milliseconds
}
```

### 11.2 Slow Request Thresholds
- Slow request: > 1000ms
- Slow query: > 1000ms
- Logged for performance monitoring

---

## 12. Integration Points

### 12.1 External Services
- **Firebase Auth**: User authentication
- **Supabase**: PostgreSQL database + storage
- **Redis**: Caching + session management
- **Google Gemini**: AI-powered features
- **WhatsApp (Evolution API)**: Patient messaging

### 12.2 Internal Services
- **Celery**: Background task processing
- **Prometheus**: Metrics collection
- **WebSocket Manager**: Real-time communication

---

## 13. Deployment Configuration

### 13.1 Railway Environment
```bash
ENVIRONMENT="production"
DEBUG="false"
HOST="0.0.0.0"
PORT="8000"
```

### 13.2 Database Connection
```bash
DATABASE_URL="postgresql+psycopg://postgres:***@db.rszpypytdciggybbpnrp.supabase.co:5432/postgres"
DB_POOL_SIZE="30"
DB_MAX_OVERFLOW="40"
DB_POOL_TIMEOUT="20"
DB_STATEMENT_TIMEOUT="30000"
DB_POOL_RECYCLE="3600"
```

### 13.3 Redis Configuration
```bash
REDIS_URL="redis://default:***@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149"
REDIS_MAX_CONNECTIONS="25"
REDIS_SOCKET_TIMEOUT="10.0"
REDIS_SSL="true"
```

---

## 14. Conclusion

The backend API is **production-ready** with:
- ✅ Comprehensive CORS configuration supporting Railway wildcard patterns
- ✅ Public `/api/config` endpoint for frontend runtime configuration
- ✅ WebSocket endpoints with proper authentication
- ✅ Firebase Authentication integration
- ✅ Proper security headers and rate limiting
- ✅ Environment variable configuration matches CORS allowed origins
- ✅ Well-structured API with consistent response formats
- ✅ Health check endpoints for monitoring
- ✅ Performance tracking and monitoring

**No critical configuration mismatches detected.**

---

## 15. Quick Reference

### Frontend Integration Checklist
- [ ] Fetch runtime config from `GET /api/config`
- [ ] Use `VITE_API_BASE_URL` for REST API calls
- [ ] Use `VITE_WS_BASE_URL` for WebSocket connections
- [ ] Include Firebase JWT in `Authorization: Bearer {token}` header
- [ ] Implement WebSocket reconnection logic
- [ ] Handle 401/403 errors with token refresh
- [ ] Implement rate limit handling (429 responses)
- [ ] Add `X-Request-ID` header for request tracing
- [ ] Cache `/api/config` response (5-minute TTL)
- [ ] Implement WebSocket ping/pong heartbeat

### Critical URLs
- API Base: `https://clinica-oncologica-v02-production.up.railway.app/api/v1`
- WebSocket: `wss://clinica-oncologica-v02-production.up.railway.app/ws/connect`
- Config: `https://clinica-oncologica-v02-production.up.railway.app/api/config`
- Health: `https://clinica-oncologica-v02-production.up.railway.app/api/v1/health`

---

**End of Analysis**
