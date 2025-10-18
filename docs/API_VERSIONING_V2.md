# 🔄 API Versioning v2 - Migration Guide

**Status**: 📋 Planned (Sprint 4)  
**Current Version**: v1  
**Target Version**: v2  
**Migration Timeline**: Q1 2025

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Why v2](#why-v2)
3. [v2 Structure](#v2-structure)
4. [Breaking Changes](#breaking-changes)
5. [Migration Strategy](#migration-strategy)
6. [Backward Compatibility](#backward-compatibility)
7. [Implementation Plan](#implementation-plan)
8. [Timeline](#timeline)

---

## 🎯 Overview

API v2 represents a modernized, cleaner API structure built on the lessons learned from v1 and the organizational improvements from Sprint 3.

### Goals

- ✅ **Cleaner Structure**: Domain-based organization from the start
- ✅ **Better Naming**: Consistent, intuitive endpoint names
- ✅ **Improved Performance**: Optimized queries and caching
- ✅ **Enhanced Security**: Updated authentication and authorization
- ✅ **Modern Standards**: REST best practices, GraphQL consideration
- ✅ **Better Documentation**: Auto-generated OpenAPI/Swagger docs

---

## 🤔 Why v2?

### Current Pain Points (v1)

1. **Inconsistent Naming**: Mix of `monthly_quiz`, `quiz`, `enhanced_quiz`
2. **Flat Structure**: All endpoints in root `/api/v1/`
3. **Legacy Cruft**: Deprecated endpoints still present
4. **Inconsistent Response**: Different error formats across endpoints
5. **Auth Complexity**: Multiple auth mechanisms

### v2 Improvements

| Aspect | v1 | v2 |
|--------|----|----|
| **Structure** | Flat | Hierarchical by domain |
| **Naming** | Inconsistent | Standardized (REST) |
| **Auth** | Mixed | Unified JWT + Firebase |
| **Errors** | Varied formats | Consistent RFC 7807 |
| **Docs** | Manual | Auto-generated |
| **Performance** | Good | Optimized |

---

## 🏗️ v2 Structure

### Directory Organization

```
app/api/v2/
├── __init__.py
│
├── core/
│   ├── __init__.py
│   ├── auth.py              # POST /api/v2/auth/login
│   ├── health.py            # GET /api/v2/health
│   └── system.py            # GET /api/v2/system/info
│
├── quiz/
│   ├── __init__.py
│   ├── admin.py             # /api/v2/quiz/admin/*
│   │   ├── POST   /api/v2/quiz/admin/create
│   │   ├── GET    /api/v2/quiz/admin/:id
│   │   ├── PUT    /api/v2/quiz/admin/:id
│   │   ├── DELETE /api/v2/quiz/admin/:id
│   │   └── GET    /api/v2/quiz/admin/statistics
│   │
│   ├── public.py            # /api/v2/quiz/public/*
│   │   ├── GET    /api/v2/quiz/public/:token
│   │   └── POST   /api/v2/quiz/public/:token/submit
│   │
│   ├── responses.py         # /api/v2/quiz/responses/*
│   │   ├── GET    /api/v2/quiz/responses
│   │   ├── GET    /api/v2/quiz/responses/:id
│   │   └── POST   /api/v2/quiz/responses/:id/export
│   │
│   └── alerts.py            # /api/v2/quiz/alerts/*
│       ├── GET    /api/v2/quiz/alerts
│       ├── POST   /api/v2/quiz/alerts/:id/acknowledge
│       └── PUT    /api/v2/quiz/alerts/:id/resolve
│
├── patients/
│   ├── __init__.py
│   ├── crud.py              # /api/v2/patients/*
│   │   ├── GET    /api/v2/patients
│   │   ├── POST   /api/v2/patients
│   │   ├── GET    /api/v2/patients/:id
│   │   ├── PUT    /api/v2/patients/:id
│   │   └── DELETE /api/v2/patients/:id
│   │
│   ├── timeline.py          # /api/v2/patients/:id/timeline
│   ├── documents.py         # /api/v2/patients/:id/documents
│   └── flows.py             # /api/v2/patients/:id/flows
│
├── messages/
│   ├── __init__.py
│   ├── send.py              # POST /api/v2/messages/send
│   ├── history.py           # GET /api/v2/messages/history
│   └── templates.py         # CRUD /api/v2/messages/templates
│
├── analytics/
│   ├── __init__.py
│   ├── dashboard.py         # GET /api/v2/analytics/dashboard
│   ├── reports.py           # GET /api/v2/analytics/reports
│   └── metrics.py           # GET /api/v2/analytics/metrics
│
├── admin/
│   ├── __init__.py
│   ├── users.py             # CRUD /api/v2/admin/users
│   ├── roles.py             # CRUD /api/v2/admin/roles
│   ├── audit.py             # GET /api/v2/admin/audit
│   └── settings.py          # GET/PUT /api/v2/admin/settings
│
├── monitoring/
│   ├── __init__.py
│   ├── health.py            # GET /api/v2/monitoring/health
│   ├── metrics.py           # GET /api/v2/monitoring/metrics
│   └── performance.py       # GET /api/v2/monitoring/performance
│
└── webhooks/
    ├── __init__.py
    ├── whatsapp.py          # POST /api/v2/webhooks/whatsapp
    └── external.py          # POST /api/v2/webhooks/external
```

### URL Structure

```
Pattern: /api/v2/{domain}/{resource}/{action}

Examples:
✅ /api/v2/patients                    # List patients
✅ /api/v2/patients/123                # Get patient
✅ /api/v2/patients/123/timeline       # Patient timeline
✅ /api/v2/quiz/admin/create           # Create quiz (admin)
✅ /api/v2/quiz/public/abc123          # Access quiz (patient)
✅ /api/v2/messages/send               # Send message
✅ /api/v2/analytics/dashboard         # Dashboard data
```

---

## 💥 Breaking Changes

### 1. URL Structure

**v1 → v2 Mapping**:

```
# Quiz Endpoints
v1: /api/v1/monthly_quiz
v2: /api/v2/quiz/admin

v1: /api/v1/monthly_quiz_public/{token}
v2: /api/v2/quiz/public/{token}

# Patient Endpoints
v1: /api/v1/patients
v2: /api/v2/patients

v1: /api/v1/patients/{id}/timeline
v2: /api/v2/patients/{id}/timeline

# Message Endpoints
v1: /api/v1/messages
v2: /api/v2/messages/send

v1: /api/v1/enhanced_messages
v2: /api/v2/messages/send (consolidated)

# Analytics
v1: /api/v1/analytics
v2: /api/v2/analytics/dashboard

v1: /api/v1/enhanced_analytics
v2: /api/v2/analytics/dashboard (consolidated)
```

### 2. Response Format

**v1 Format** (inconsistent):
```json
{
  "data": {...},
  "success": true
}

// OR

{
  "result": {...},
  "status": "ok"
}
```

**v2 Format** (consistent):
```json
{
  "data": {...},
  "meta": {
    "version": "2.0",
    "timestamp": "2025-01-15T10:30:00Z",
    "requestId": "req_abc123"
  }
}
```

### 3. Error Format

**v1 Format**:
```json
{
  "error": "Something went wrong",
  "status": 400
}
```

**v2 Format** (RFC 7807):
```json
{
  "type": "https://api.hormonia.com/errors/validation-error",
  "title": "Validation Error",
  "status": 400,
  "detail": "Invalid patient CPF format",
  "instance": "/api/v2/patients",
  "traceId": "trace_xyz789",
  "errors": [
    {
      "field": "cpf",
      "message": "CPF must be in format XXX.XXX.XXX-XX"
    }
  ]
}
```

### 4. Authentication

**v1**: Mixed JWT and Firebase
**v2**: Unified approach with clear token format

```
v1: Bearer {token}
v2: Bearer {token} (but validated differently)

New: Refresh token endpoint
New: Token introspection endpoint
```

### 5. Pagination

**v1**:
```
?page=1&size=20
```

**v2** (cursor-based):
```
?cursor=abc123&limit=20

Response:
{
  "data": [...],
  "pagination": {
    "nextCursor": "xyz789",
    "hasMore": true
  }
}
```

---

## 🔄 Migration Strategy

### Phase 1: Development (Sprint 4)

**Duration**: 2 weeks

1. ✅ Create `app/api/v2/` structure
2. ✅ Implement core endpoints (auth, health)
3. ✅ Set up v2 router in main.py
4. ✅ Create v2 schemas (Pydantic models)
5. ✅ Implement response/error standards
6. ✅ Write migration scripts
7. ✅ Update documentation

**Deliverables**:
- v2 endpoint structure
- Core v2 endpoints working
- Migration guide
- Auto-generated API docs

### Phase 2: Migration (Sprint 5)

**Duration**: 2 weeks

1. ✅ Migrate quiz endpoints to v2
2. ✅ Migrate patient endpoints to v2
3. ✅ Migrate message endpoints to v2
4. ✅ Update frontend to use v2
5. ✅ Run parallel v1/v2 testing
6. ✅ Performance testing
7. ✅ Load testing

**Deliverables**:
- All core endpoints migrated
- Frontend using v2
- Performance benchmarks
- Test results

### Phase 3: Deprecation (Sprint 6)

**Duration**: 4 weeks (deprecation period)

1. ✅ Announce v1 deprecation
2. ✅ Add deprecation warnings to v1
3. ✅ Monitor v1 usage
4. ✅ Assist clients with migration
5. ✅ Final migration push

**Deliverables**:
- Deprecation notices
- Migration support
- Usage analytics
- Client migration status

### Phase 4: Sunset (Sprint 7)

**Duration**: 1 week

1. ✅ Remove v1 endpoints
2. ✅ Update documentation
3. ✅ Remove deprecated code
4. ✅ Cleanup

**Deliverables**:
- v1 completely removed
- Clean codebase
- Updated docs

---

## 🔙 Backward Compatibility

### Dual-Running Period

**Timeline**: 6 weeks (Sprints 5-6)

During this period:
- ✅ Both v1 and v2 run simultaneously
- ✅ v1 serves existing clients
- ✅ v2 serves new clients and migrated clients
- ✅ Monitoring tracks usage of both versions

### v1 → v2 Proxy

Create compatibility layer for gradual migration:

```python
# app/api/v1/compat.py
from fastapi import APIRouter
from app.api.v2 import quiz as quiz_v2

router = APIRouter()

@router.get("/monthly_quiz")
async def monthly_quiz_compat():
    """
    Deprecated: Use /api/v2/quiz/admin instead
    
    This endpoint proxies to v2 for backward compatibility.
    Will be removed in Sprint 7.
    """
    # Add deprecation header
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2025-03-31"
    response.headers["Link"] = "</api/v2/quiz/admin>; rel=\"successor-version\""
    
    # Proxy to v2
    return await quiz_v2.admin.list_quizzes()
```

### Migration Helper

```python
# scripts/migrate_to_v2.py

import re

def migrate_url(v1_url: str) -> str:
    """Convert v1 URL to v2 URL."""
    
    migrations = {
        r'/api/v1/monthly_quiz': '/api/v2/quiz/admin',
        r'/api/v1/monthly_quiz_public/(.+)': r'/api/v2/quiz/public/\1',
        r'/api/v1/patients': '/api/v2/patients',
        r'/api/v1/messages': '/api/v2/messages/send',
        r'/api/v1/analytics': '/api/v2/analytics/dashboard',
    }
    
    for old_pattern, new_url in migrations.items():
        if re.match(old_pattern, v1_url):
            return re.sub(old_pattern, new_url, v1_url)
    
    return v1_url  # No migration found
```

---

## 📝 Implementation Plan

### Sprint 4: v2 Foundation

**Week 1**:
- [ ] Create v2 directory structure
- [ ] Implement v2 response/error standards
- [ ] Set up v2 router
- [ ] Implement core endpoints (auth, health)
- [ ] Write v2 schemas

**Week 2**:
- [ ] Implement quiz v2 endpoints
- [ ] Implement patient v2 endpoints
- [ ] Write tests for v2 endpoints
- [ ] Set up OpenAPI/Swagger for v2
- [ ] Write migration guide

### Sprint 5: Migration

**Week 1**:
- [ ] Migrate frontend to v2 quiz endpoints
- [ ] Migrate frontend to v2 patient endpoints
- [ ] Run parallel v1/v2 testing
- [ ] Performance testing

**Week 2**:
- [ ] Migrate remaining endpoints
- [ ] Complete frontend migration
- [ ] Load testing
- [ ] Security audit

### Sprint 6: Deprecation Period

**Weeks 1-4**:
- [ ] Monitor v1/v2 usage
- [ ] Assist with client migrations
- [ ] Add deprecation warnings
- [ ] Prepare for v1 sunset

### Sprint 7: v1 Sunset

**Week 1**:
- [ ] Remove v1 endpoints
- [ ] Remove compatibility layer
- [ ] Update documentation
- [ ] Cleanup codebase

---

## 📅 Timeline

```
Sprint 4 (Weeks 1-2):  Foundation + Core Endpoints
├── v2 structure created
├── Core endpoints implemented
├── OpenAPI docs generated
└── Migration scripts ready

Sprint 5 (Weeks 3-4):  Migration + Testing
├── All endpoints migrated
├── Frontend fully on v2
├── Performance validated
└── Security audited

Sprint 6 (Weeks 5-8):  Deprecation Period
├── v1 deprecated warnings
├── Dual running v1/v2
├── Client migration support
└── Usage monitoring

Sprint 7 (Week 9):     v1 Sunset
├── v1 removed
├── Codebase cleaned
├── Docs updated
└── v2 only
```

---

## 🎯 Success Criteria

### Technical

- [ ] All v1 endpoints have v2 equivalents
- [ ] 100% test coverage on v2 endpoints
- [ ] Performance equal or better than v1
- [ ] OpenAPI/Swagger docs generated
- [ ] Zero breaking changes during migration

### Business

- [ ] 100% client migration complete
- [ ] Zero downtime during migration
- [ ] Improved developer experience
- [ ] Better API documentation
- [ ] Faster response times

---

## 📊 Monitoring

### Metrics to Track

```python
# v1 vs v2 Usage
- requests_v1_total
- requests_v2_total
- migration_percentage

# Performance
- response_time_v1
- response_time_v2
- error_rate_v1
- error_rate_v2

# Adoption
- clients_on_v1
- clients_on_v2
- endpoints_migrated
```

### Dashboards

1. **Migration Dashboard**
   - v1 vs v2 traffic
   - Migration percentage
   - Top v1 endpoints still in use

2. **Performance Dashboard**
   - Response times comparison
   - Error rates comparison
   - Throughput comparison

3. **Adoption Dashboard**
   - Clients migrated
   - Endpoints usage
   - Deprecation warnings triggered

---

## 🔐 Security Improvements in v2

1. **Unified Authentication**: Single JWT + Firebase flow
2. **Rate Limiting**: Per-endpoint configurable limits
3. **Input Validation**: Stricter Pydantic models
4. **CORS**: More granular control
5. **CSRF**: Token-based protection
6. **API Keys**: Support for service-to-service auth

---

## 📚 Documentation

### Auto-Generated Docs

**OpenAPI/Swagger**:
```
GET /api/v2/docs          # Swagger UI
GET /api/v2/redoc         # ReDoc UI
GET /api/v2/openapi.json  # OpenAPI schema
```

**Features**:
- ✅ Interactive API explorer
- ✅ Try-it-out functionality
- ✅ Schema validation
- ✅ Example requests/responses
- ✅ Authentication testing

---

## 🎓 Best Practices

### v2 Endpoint Checklist

- [ ] RESTful URL structure
- [ ] Consistent response format
- [ ] RFC 7807 error format
- [ ] OpenAPI annotations
- [ ] Input validation (Pydantic)
- [ ] Output serialization
- [ ] Authentication required
- [ ] Authorization checked
- [ ] Rate limiting applied
- [ ] Logging added
- [ ] Tests written (unit + integration)
- [ ] Performance tested
- [ ] Documentation complete

---

## 🔮 Future: GraphQL Consideration

After v2 stabilizes, consider GraphQL:

**Benefits**:
- Client specifies exact data needed
- Single endpoint
- Strongly typed
- Real-time subscriptions

**Trade-offs**:
- More complex setup
- Caching challenges
- Learning curve

**Decision**: Evaluate in Sprint 10+

---

## 📞 Support

### For Developers

- **Documentation**: `/api/v2/docs`
- **Migration Guide**: This document
- **Support**: #api-v2 Slack channel

### For Clients

- **Migration Timeline**: Communicated via email
- **Breaking Changes**: Documented in changelog
- **Support**: api-support@hormonia.com

---

## ✅ Checklist

### Planning Phase ✅

- [x] Document v2 structure
- [x] Define breaking changes
- [x] Create migration strategy
- [x] Write timeline

### Sprint 4 (Implementation)

- [ ] Create v2 directory structure
- [ ] Implement core v2 endpoints
- [ ] Set up OpenAPI/Swagger
- [ ] Write migration scripts
- [ ] Update documentation

### Sprint 5 (Migration)

- [ ] Migrate all endpoints
- [ ] Update frontend
- [ ] Performance testing
- [ ] Security audit

### Sprint 6 (Deprecation)

- [ ] Add v1 deprecation warnings
- [ ] Monitor usage
- [ ] Client migration support

### Sprint 7 (Sunset)

- [ ] Remove v1 endpoints
- [ ] Cleanup codebase
- [ ] Update all documentation

---

**Status**: 📋 Planned for Sprint 4  
**Owner**: Backend Team  
**Timeline**: Sprints 4-7 (9 weeks)  
**Priority**: High

---

*"Evolution, not revolution. Migrate gradually, maintain compatibility, deliver value."*

🚀 **Ready for v2!**