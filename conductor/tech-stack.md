# Tech Stack

## Backend
- **Language:** Python 3.13
- **Framework:** FastAPI
- **Task Queue:** Celery with Redis broker
- **ORM:** SQLAlchemy 2.0
- **Database:** PostgreSQL 15+
- **Migration Tool:** Alembic
- **Validation:** Pydantic v2
- **Testing:** Pytest

## Frontend (Dashboard)
- **Library:** React 19
- **Build Tool:** Vite 6
- **Language:** TypeScript
- **Styling:** TailwindCSS 4
- **UI Components:** Radix UI / shadcn/ui
- **State Management:** TanStack Query (React Query)
- **Routing:** React Router 6
- **Testing:** Vitest, Playwright

## Quiz Interface
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** TailwindCSS
- **UI Components:** Radix UI
- **Testing:** Jest

## Infrastructure & Services
- **Authentication:** Firebase Auth
- **Messaging:** Evolution API (WhatsApp)
- **Monitoring/Logging:** Sentry, Prometheus/Flower
- **Resilience:** aiobreaker (Circuit Breaker), tenacity (Retry)
- **Deployment:** Railway (RAILPACK)
