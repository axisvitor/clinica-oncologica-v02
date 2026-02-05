# Backend API Documentation

Welcome to the **Hormonia Backend** documentation. This repository contains all technical details, API specifications, and maintenance guides for the Python/FastAPI backend system.

## 📂 Directory Structure

### 🏗️ [Architecture](./architecture)
Core system design, database schemas, and infrastructure docs.
- **Database**: [Models](./architecture/database-models-analysis-report.md), [Tables](./architecture/database-tables-complete-analysis.md)
- **Middleware**: [Security](./architecture/security-middleware-implementation.md), [Auth](./architecture/auth-middleware-analysis.md)
- **Infrastructure**: [Redis](./architecture/redis-implementation-guide.md), [Deployment](./architecture/deployment-strategy.md)

### 📜 [API Specifications](./specs)
Specific documentation for API routes and functionality.
- [Auth Routes](./specs/auth-routes-analysis-report.md)
- [Patient Routes](./specs/patient-routes-analysis.md)

### 📘 [Guides & Operations](./guides)
Operational manuals and developer guides.
- **Development**: [Setup Guide](./guides/development-environment-setup.md)
- **Operations**: [Maintenance](./guides/operational-maintenance.md)
- **Deployment**: [Production Guide](./guides/deployment-checklist.md)

### 🚀 [Features](./features)
Documentation grouped by specific backend features.
- **[Alerts](./features/alerts)**: System notifications and alert logic.
- **[Patient](./features/patient)**: Patient management logic.
- **[WhatsApp](./features/whatsapp)**: WhatsApp integration details.

### 📊 [Reports](./reports)
Historical analysis, test results, and debugging logs.
- **[Debug](./reports/debug)**: Session logs and error analysis.
- **[Performance](./reports/performance)**: Benchmark reports.
- **[Quality](./reports/quality)**: Code quality reviews.
- **[Security](./reports/security)**: Security audits.
- **[Testing](./reports/testing)**: Test execution reports.

### 📁 Legacy & Repo
- **[Repo](./repo)**: Repository analysis and metadata.
- **[.refactor](./.refactor)**: Internal refactoring logs.

---

> [!IMPORTANT]
> **Deprecation Notice (2026-01-04):**
> - References to `saga_orchestrator.py` in older docs are outdated. Use `app/orchestration/saga_orchestrator/` package instead.
> - Tables `quiz_sessions_v2`, `quiz_template_versions_v2`, `quiz_questions` have been dropped.
> - Phone normalization now uses E.164 format exclusively.

*Backend documentation last updated: 2026-01-04.*
