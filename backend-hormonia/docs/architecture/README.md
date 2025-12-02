# Architecture Documentation

Comprehensive architecture documentation for the Clínica Hormonia oncology management system.

## Quick Links

- **[Architecture Decision Records (ADRs)](./decisions/README.md)** - Key architectural decisions and rationale
- **[System Overview](#system-overview)** - High-level architecture
- **[Component Diagrams](#component-diagrams)** - System components and interactions
- **[Data Flow](#data-flow)** - How data moves through the system
- **[Security Architecture](#security-architecture)** - Security measures and compliance

## System Overview

Clínica Hormonia is a comprehensive oncology patient management system built with:

- **Backend**: FastAPI (Python 3.13+) with Clean Architecture
- **Database**: PostgreSQL 15+ with Row-Level Security (RLS)
- **Cache**: Redis 7+ for caching and rate limiting
- **Background Tasks**: Celery + Beat for async processing
- **Authentication**: Firebase Admin SDK
- **Messaging**: Evolution API for WhatsApp integration

### Architecture Principles

Following **Clean Architecture** and **SOLID** principles:

1. **Separation of Concerns**: Clear layer boundaries (Domain → Application → Infrastructure → Presentation)
2. **Dependency Inversion**: High-level modules don't depend on low-level modules
3. **Testability**: Business logic isolated from infrastructure
4. **Scalability**: Horizontal scaling with stateless services
5. **Security First**: Multi-layer security scanning and RLS at database level

## Component Diagrams

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Presentation Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Frontend   │  │   REST API   │  │  WebSocket   │      │
│  │   (React)    │  │  (FastAPI)   │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Use Cases   │  │     DTOs     │  │ Interfaces   │      │
│  │  (Services)  │  │              │  │ (Contracts)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                       Domain Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Entities   │  │    Events    │  │ Value Objects│      │
│  │   (Models)   │  │              │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  PostgreSQL  │  │    Redis     │  │   Celery     │      │
│  │     RLS      │  │   Caching    │  │  Background  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Firebase   │  │ Evolution API│  │     SMTP     │      │
│  │     Auth     │  │   WhatsApp   │  │    Email     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow: Patient Quiz Journey

```
Patient ──WhatsApp──> Evolution API ──Webhook──> FastAPI
                                                    │
                                                    ├──> Authentication (Firebase)
                                                    │
                                                    ├──> Use Case (Application Layer)
                                                    │
                                                    ├──> Domain Logic (Business Rules)
                                                    │
                                                    ├──> Repository (Infrastructure)
                                                    │
                                                    ├──> PostgreSQL (RLS enforced)
                                                    │
                                                    ├──> Cache (Redis)
                                                    │
                                                    └──> Background Task (Celery)
                                                          │
                                                          ├──> Email Notification
                                                          └──> WhatsApp Message
```

## Security Architecture

### 7-Layer Security Model

Following **ADR-0010**, we implement security at 7 layers:

1. **Secret Scanning**: TruffleHog, GitGuardian
2. **Dependency Scanning**: Safety, pip-audit, npm audit
3. **SAST**: Bandit, Semgrep, ESLint security
4. **Container Scanning**: Trivy, Anchore
5. **IaC Scanning**: tfsec, Checkov
6. **DAST**: OWASP ZAP, Nuclei
7. **Runtime Monitoring**: Sentry, Falco

### Authentication Flow

```
User ──Login──> Frontend ──Firebase SDK──> Firebase Auth
                                                │
                                                ├──> ID Token (JWT)
                                                │
Frontend ──API Request + Token──> FastAPI Middleware
                                        │
                                        ├──> Verify Token (Firebase Admin SDK)
                                        │
                                        ├──> Extract Claims (role, physician_id)
                                        │
                                        └──> Set RLS Context (PostgreSQL)
                                              │
                                              └──> Query (automatic filtering by physician)
```

### Data Security: Row-Level Security (RLS)

All patient data is isolated by physician using PostgreSQL RLS:

```sql
-- Enable RLS
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;

-- Policy: Physicians see only their patients
CREATE POLICY physician_isolation ON patients
    FOR ALL
    USING (physician_id = current_setting('app.current_physician_id')::uuid);
```

## Key Architectural Decisions

All major architectural decisions are documented as ADRs:

- **[ADR-0001: FastAPI Framework](./decisions/ADR-0001-fastapi-framework.md)** - Why FastAPI over Django/Flask
- **[ADR-0002: PostgreSQL RLS](./decisions/ADR-0002-postgresql-rls.md)** - Multi-tenancy with RLS
- **[ADR-0003: Redis Caching](./decisions/ADR-0003-redis-caching.md)** - Caching and rate limiting
- **[ADR-0004: Celery Background Tasks](./decisions/ADR-0004-celery-background-tasks.md)** - Async task processing
- **[ADR-0005: Evolution API](./decisions/ADR-0005-evolution-api-whatsapp.md)** - WhatsApp integration
- **[ADR-0006: Firebase Authentication](./decisions/ADR-0006-firebase-authentication.md)** - Auth strategy
- **[ADR-0007: SPARC Methodology](./decisions/ADR-0007-sparc-methodology.md)** - Development process
- **[ADR-0008: Hive Mind](./decisions/ADR-0008-hive-mind-coordination.md)** - AI agent coordination
- **[ADR-0009: Clean Architecture](./decisions/ADR-0009-clean-architecture.md)** - Layered architecture
- **[ADR-0010: Multi-Layer Security](./decisions/ADR-0010-multi-layer-security.md)** - Security scanning

See [full ADR index](./decisions/README.md) for complete list.

## Technology Stack

### Backend
- **Language**: Python 3.13+
- **Framework**: FastAPI 0.104+
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Validation**: Pydantic v2

### Database
- **Primary**: PostgreSQL 15+
- **Features**: RLS, JSONB, GIN indexes, partitioning
- **Pooling**: PgBouncer

### Caching & Queues
- **Cache**: Redis 7+
- **Task Queue**: Celery 5+
- **Scheduler**: Celery Beat

### External Services
- **Authentication**: Firebase Admin SDK
- **WhatsApp**: Evolution API v2
- **Email**: SMTP (SendGrid/AWS SES)
- **Monitoring**: Sentry, Prometheus

### Infrastructure
- **Containers**: Docker, Docker Compose
- **Orchestration**: (Future) Kubernetes
- **CI/CD**: GitHub Actions
- **Cloud**: (Planned) AWS/GCP

## Development Methodology

We follow **SPARC methodology** (ADR-0007):

1. **Specification**: Define requirements
2. **Pseudocode**: Design algorithms
3. **Architecture**: Design system structure
4. **Refinement**: Implement with TDD
5. **Completion**: Integrate and document

### Multi-Agent Development

Using **Hive Mind** (ADR-0008) for coordinated AI-assisted development:
- Parallel agent execution (2.8-4.4x faster)
- Specialized agents (coder, tester, reviewer, architect)
- Collective memory for context sharing
- Consensus mechanisms for decisions

## Performance Targets

- **API Response Time**: <200ms (p95)
- **Database Query Time**: <50ms (p95)
- **Cache Hit Ratio**: >80%
- **Background Task Latency**: <5s
- **Concurrent Users**: 1000+
- **Test Coverage**: >80%

## Compliance

### HIPAA (Health Insurance Portability and Accountability Act)
- ✅ Encryption at rest and in transit
- ✅ Audit logging of all data access
- ✅ Row-level security for data isolation
- ✅ Secure authentication (MFA support)
- ✅ Regular security scanning
- ✅ Incident response procedures

### LGPD (Lei Geral de Proteção de Dados - Brazil)
- ✅ Data minimization
- ✅ Purpose limitation
- ✅ User consent management
- ✅ Right to erasure
- ✅ Data portability
- ✅ Privacy by design

## Monitoring & Observability

### Application Monitoring
- **Error Tracking**: Sentry
- **Logging**: Structured JSON logs
- **Metrics**: Prometheus + Grafana
- **Tracing**: (Planned) OpenTelemetry

### Database Monitoring
- **Query Performance**: pg_stat_statements
- **Slow Query Log**: PostgreSQL logs
- **Connection Pooling**: PgBouncer metrics

### Infrastructure Monitoring
- **Container Health**: Docker stats
- **Redis**: Redis INFO
- **Celery**: Flower dashboard

## Disaster Recovery

### Backup Strategy
- **Database**: Automated daily backups (30-day retention)
- **Files**: S3 bucket with versioning
- **Configurations**: Version controlled in Git

### RTO/RPO Targets
- **Recovery Time Objective (RTO)**: 4 hours
- **Recovery Point Objective (RPO)**: 1 hour

## Scalability Plan

### Current Architecture
- Vertical scaling (single server)
- Connection pooling (PgBouncer)
- Read replicas for reporting

### Future Enhancements (>10,000 users)
- Horizontal scaling with load balancer
- Database sharding by physician
- Microservices for heavy operations
- CDN for static assets
- Kubernetes orchestration

## Repository Refactoring Projects

### Patient Repository Refactoring (Active)

**Status**: 📋 Ready for Implementation
**Effort**: 8 weeks (4 developers)
**ROI**: 12-18 months

The Patient Repository has grown to a 1,015-line God Class that violates Single Responsibility Principle. We're refactoring it into 4 specialized repositories following the Repository Segregation Pattern.

**Documentation Suite** (2,711 lines total):
- **[Executive Summary](./PATIENT_REPOSITORY_REFACTORING_SUMMARY.md)** (557 lines) - Business case, ROI, timeline
- **[Refactoring Plan](./PATIENT_REPOSITORY_REFACTORING_PLAN.md)** (770 lines) - Complete architecture and migration strategy
- **[Implementation Guide](./PATIENT_REPOSITORY_IMPLEMENTATION_GUIDE.md)** (885 lines) - Step-by-step code examples
- **[Method Matrix](./PATIENT_REPOSITORY_METHOD_MATRIX.md)** (499 lines) - Reference guide and migration mapping

**Key Benefits**:
- 75% complexity reduction per file (1,015 → ~250 lines avg)
- 73% reduction in cyclomatic complexity (158 → ~42 avg)
- $125K annual savings (maintenance + infrastructure)
- 50% faster bug fixes and feature development

**Quick Start**:
1. **Stakeholders**: Read [Executive Summary](./PATIENT_REPOSITORY_REFACTORING_SUMMARY.md)
2. **Developers**: Read [Implementation Guide](./PATIENT_REPOSITORY_IMPLEMENTATION_GUIDE.md)
3. **Reference**: Bookmark [Method Matrix](./PATIENT_REPOSITORY_METHOD_MATRIX.md)

---

## Related Documentation

- **[API Documentation](../api/README.md)** - REST API specifications
- **[Database Schema](../database/README.md)** - Database design
- **[Deployment Guide](../operations/README.md)** - Operations and deployment
- **[Development Guide](../guides/README.md)** - Development setup and workflow

## Contributing

When making architectural changes:

1. **Create an ADR**: Document major decisions (see [ADR README](./decisions/README.md))
2. **Review Process**: Get architecture team approval
3. **Update Diagrams**: Keep architecture diagrams current
4. **Document Trade-offs**: Explain pros/cons of decisions
5. **Consider Impact**: Assess security, performance, and compliance

---

**Architecture Team**: @backend-team, @security-team, @devops-team
**Last Updated**: 2024-01-24
**Next Review**: 2024-04-24 (quarterly)
