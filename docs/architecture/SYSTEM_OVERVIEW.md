# System Architecture Overview

**Project**: Clínica Oncológica - Sistema Hormonia
**Version**: 2.0
**Last Updated**: 2025-11-12

## Executive Summary

Sistema Hormonia is an AI-powered patient communication and monitoring platform designed for oncology clinics specializing in hormone therapy. The system automates patient engagement, collects clinical data through intelligent assessments, and provides real-time insights to healthcare professionals.

## System Components

### 1. Backend (FastAPI/Python 3.13)
**Location**: `/backend-hormonia`

The backend is a modular FastAPI application featuring:
- **Core Architecture**: Factory pattern with modular components
- **API Layer**: RESTful endpoints organized by domain (v1 & v2)
- **Business Logic**: Service layer with clean separation of concerns
- **Data Layer**: SQLAlchemy ORM with PostgreSQL
- **Async Processing**: Celery for background tasks
- **Caching**: Dual Redis client (sync/async)
- **AI Integration**: Google Gemini for intelligent responses

**Key Features**:
- Thread-safe session management
- Comprehensive authentication (JWT + refresh tokens)
- Row-level security (RLS) with 7 role types
- Real-time WebSocket updates
- Intelligent caching (84.8% performance improvement)

### 2. Frontend (React/TypeScript)
**Location**: `/frontend-hormonia`

Modern React SPA with:
- **UI Framework**: React 18 with TypeScript
- **Styling**: Tailwind CSS + shadcn/ui components
- **State Management**: React Query for server state
- **Routing**: React Router v6
- **Build Tool**: Vite
- **Testing**: Vitest + Playwright

**Key Features**:
- Real-time dashboard for patient monitoring
- Interactive analytics and insights
- Message composition and flow management
- Quiz template creation and analysis
- Comprehensive reporting system

### 3. Quiz Interface (Next.js)
**Location**: `/quiz-mensal-interface`

Public-facing quiz interface for patients:
- **Framework**: Next.js 14 with App Router
- **UI**: Tailwind CSS + shadcn/ui
- **Session Management**: Secure token-based sessions
- **Offline Support**: Progressive Web App (PWA)

**Key Features**:
- Secure public access (no login required)
- Session persistence and resume capability
- CSRF protection
- Mobile-optimized responsive design

## Architecture Patterns

### Microservices Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     Load Balancer / CDN                      │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐   ┌────────▼────────┐   ┌──────▼──────┐
│   Frontend     │   │   Quiz Public   │   │   Backend   │
│   (React)      │   │   (Next.js)     │   │   (FastAPI) │
└───────┬────────┘   └────────┬────────┘   └──────┬──────┘
        │                     │                     │
        └─────────────────────┴─────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   Shared Services  │
                    ├────────────────────┤
                    │ PostgreSQL         │
                    │ Redis              │
                    │ Celery Workers     │
                    │ Evolution API      │
                    │ Google Gemini      │
                    └────────────────────┘
```

### Data Flow

```
Patient WhatsApp
     │
     ▼
Evolution API ──► Backend ──► AI Processing (Gemini)
                   │    │
                   │    ▼
                   │  Message Queue (Celery)
                   │    │
                   ▼    ▼
              PostgreSQL + Redis
                   │
                   ▼
              Frontend Dashboard
                   │
                   ▼
           Healthcare Professional
```

## Technology Stack

### Backend
- **Framework**: FastAPI 0.104+
- **Language**: Python 3.13
- **Database**: PostgreSQL (via Supabase)
- **Cache**: Redis 7.0+
- **Task Queue**: Celery + Redis
- **AI**: Google Gemini Pro
- **Authentication**: JWT + Firebase
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Testing**: Pytest

### Frontend
- **Framework**: React 18 + TypeScript
- **Build**: Vite 5
- **Styling**: Tailwind CSS 3
- **UI Components**: shadcn/ui
- **State**: React Query + Context
- **Testing**: Vitest + Playwright
- **Charts**: Recharts

### Quiz Interface
- **Framework**: Next.js 14
- **Styling**: Tailwind CSS
- **UI**: shadcn/ui components
- **Session**: JWT tokens
- **PWA**: next-pwa

### Infrastructure
- **Hosting**: Railway (backend + frontend)
- **Database**: Supabase (PostgreSQL)
- **Cache**: Redis Cloud
- **WhatsApp**: Evolution API (self-hosted)
- **Monitoring**: Custom dashboard + logs
- **CI/CD**: GitHub Actions

## Security Architecture

### Authentication & Authorization
- **JWT Tokens**: Access (30min) + Refresh (7 days)
- **Role-Based Access**: 7 roles (admin, doctor, patient, etc.)
- **Row-Level Security**: PostgreSQL RLS policies
- **Token Blacklist**: Redis-based revocation
- **CSRF Protection**: Token-based for public endpoints

### Data Security
- **Encryption in Transit**: TLS 1.3
- **Encryption at Rest**: Database-level encryption
- **PII Protection**: HIPAA-compliant data handling
- **Audit Logging**: Comprehensive audit trail
- **Rate Limiting**: IP-based throttling

### API Security
- **CORS**: Strict origin validation
- **Security Headers**: HSTS, CSP, X-Frame-Options
- **Input Validation**: Pydantic schemas
- **SQL Injection**: ORM parameterization
- **XSS Protection**: Content sanitization

## Database Architecture

### Core Tables
- **users**: Healthcare professionals and admin
- **patients**: Patient registry
- **messages**: WhatsApp communication log
- **flows**: Conversation flow definitions
- **quiz_sessions**: Assessment sessions
- **quiz_responses**: Patient responses
- **alerts**: Clinical alerts and notifications
- **audit_logs**: System audit trail

### Performance Optimizations
- **GIN Indexes**: JSONB column indexing
- **Eager Loading**: Relationship optimization
- **Connection Pooling**: SQLAlchemy pool management
- **Query Caching**: Redis-based query cache

## Integration Architecture

### External Services

#### 1. Evolution API (WhatsApp)
- **Purpose**: WhatsApp Business API integration
- **Communication**: REST API + Webhooks
- **Features**: Send/receive messages, media, status
- **Security**: API key authentication

#### 2. Google Gemini
- **Purpose**: AI-powered response generation
- **Model**: Gemini Pro
- **Features**: Contextual responses, content analysis
- **Optimization**: Intelligent caching (84.8% hit rate)

#### 3. Supabase
- **Purpose**: PostgreSQL hosting + authentication
- **Features**: Database, RLS, real-time subscriptions
- **Backup**: Automated daily backups

#### 4. Firebase
- **Purpose**: Authentication provider
- **Features**: User management, token validation
- **Integration**: Backend JWT validation

## Scalability Considerations

### Horizontal Scaling
- **Backend**: Stateless workers behind load balancer
- **Frontend**: CDN distribution
- **Database**: Read replicas for analytics
- **Cache**: Redis Cluster for high availability

### Performance Targets
- **API Response Time**: < 200ms (p95)
- **Dashboard Load Time**: < 2s
- **Message Processing**: < 500ms
- **Concurrent Users**: 1,000+
- **Message Throughput**: 10,000/hour

## Monitoring & Observability

### Health Checks
- **Backend**: `/health` endpoint
- **Database**: Connection pool monitoring
- **Redis**: Health and latency checks
- **Celery**: Worker status monitoring

### Logging
- **Application Logs**: Structured JSON logging
- **Access Logs**: Request/response tracking
- **Error Logs**: Exception tracking with stack traces
- **Audit Logs**: Security-relevant events

### Metrics
- **Performance**: Response times, throughput
- **Errors**: Error rates, types, trends
- **Business**: Patient engagement, quiz completion
- **Infrastructure**: CPU, memory, disk usage

## Development Workflow

### Environment Setup
1. Clone repository
2. Setup virtual environments
3. Configure environment variables
4. Initialize databases
5. Start development servers

### Git Workflow
- **Main Branch**: `main` (production)
- **Development**: `develop` (staging)
- **Features**: `feature/*` branches
- **Hotfixes**: `hotfix/*` branches

### CI/CD Pipeline
1. **PR Created**: Automated tests run
2. **Code Review**: Team review required
3. **Merge to Develop**: Deploy to staging
4. **Merge to Main**: Deploy to production

## Documentation Structure

```
/
├── README.md                          # Project overview
├── CLAUDE.md                          # AI development guidelines
├── docs/
│   ├── architecture/                  # System architecture
│   ├── guides/                        # Development guides
│   ├── deployment/                    # Deployment instructions
│   ├── security/                      # Security documentation
│   └── development/                   # Development workflows
│
├── backend-hormonia/
│   ├── README.md                      # Backend overview
│   └── docs/                          # Backend-specific docs
│       ├── api/                       # API documentation
│       ├── architecture/              # Backend architecture
│       ├── guides/                    # Backend guides
│       ├── operations/                # Operations & monitoring
│       ├── reference/                 # Technical references
│       └── archive/                   # Historical docs
│
├── frontend-hormonia/
│   └── README.md                      # Frontend overview
│
└── quiz-mensal-interface/
    └── README.md                      # Quiz interface overview
```

## Key Design Decisions

### 1. Modular Backend Architecture
**Decision**: Factory pattern with modular components
**Rationale**: Improved maintainability, testability, and scalability
**Impact**: 40% reduction in code complexity

### 2. Dual Redis Clients
**Decision**: Separate sync/async Redis clients
**Rationale**: Support both sync and async code paths
**Impact**: 84.8% cache hit rate, significant performance improvement

### 3. Row-Level Security
**Decision**: PostgreSQL RLS for multi-tenant security
**Rationale**: Database-level security enforcement
**Impact**: HIPAA compliance, reduced security vulnerabilities

### 4. Separate Quiz Interface
**Decision**: Standalone Next.js app for public quiz
**Rationale**: Security isolation, better performance
**Impact**: Zero-trust architecture for patient data

### 5. AI Caching Strategy
**Decision**: Intelligent Gemini response caching
**Rationale**: Cost reduction and performance improvement
**Impact**: 84.8% cache hit rate, 90% cost reduction

## Future Roadmap

### Short-term (3 months)
- [ ] Mobile app (React Native)
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Appointment scheduling integration

### Mid-term (6 months)
- [ ] Telemedicine integration
- [ ] Electronic health records (EHR) integration
- [ ] Advanced AI features (predictive analytics)
- [ ] Multi-clinic support

### Long-term (12 months)
- [ ] Blockchain for audit trail
- [ ] Machine learning for treatment optimization
- [ ] Patient portal expansion
- [ ] International expansion

## References

- **Backend Documentation**: `/backend-hormonia/docs/README.md`
- **API Reference**: `/backend-hormonia/docs/api/API.md`
- **Frontend Documentation**: `/frontend-hormonia/README.md`
- **Quiz Interface**: `/quiz-mensal-interface/README.md`
- **Deployment Guide**: `/docs/deployment/DEPLOYMENT.md`

---

**Last Reviewed**: 2025-11-12
**Maintained By**: Development Team
**Status**: Production
