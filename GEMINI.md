# GEMINI.md - Context & Instructions

This file serves as the primary context for the Gemini agent working on the `clinica-oncologica-v02-1` project.

## 1. Project Overview

**Architecture:** Monorepo with three main components:
*   **Backend (`backend-hormonia`):** Python 3.13 + FastAPI + Celery + PostgreSQL + Redis.
*   **Frontend (`frontend-hormonia`):** React 19 + Vite 6 + TailwindCSS.
*   **Quiz Interface (`quiz-mensal-interface`):** Next.js 14 + TailwindCSS.

**Deployment:** Railway (configured via `railway.toml` using `RAILPACK` builder).

## 2. Operational Guidelines (CRITICAL)

**File & System Safety:**
*   **NEVER** save working files, notes, or test artifacts to the root directory. Use `docs/`, `tests/`, or `scripts/` as appropriate.
*   **NEVER** hardcode secrets. Always use environment variables.
*   **Batch Operations:** When possible, combine multiple file reads, writes, or shell commands into a single turn to save context and time.

**Conventions:**
*   **Backend:** Follow PEP 8. Use type hints. Tests via `pytest`.
*   **Frontend:** Functional components with hooks. `shadcn/ui` (Radix UI) patterns. Tests via `vitest`.
*   **Quiz:** Next.js App Router patterns. Tests via `jest`.

## 3. Command Reference

### Backend (`/backend-hormonia`)
*   **Install:** `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
*   **Run Dev:** `uvicorn app.main:app --reload --port 8000`
*   **Run Full System (Worker/Beat):** [See Running Backend Guide](docs/guides/running_backend.md)
*   **Migrations:** `alembic upgrade head`
*   **Test:** `pytest`
*   **Lint/Format:** `ruff check .` (implied from typical python setups, though not explicitly in scripts, verify if needed)

### Frontend (`/frontend-hormonia`)
*   **Install:** `npm install`
*   **Run Dev:** `npm run dev` (Vite)
*   **Build:** `npm run build:prod`
*   **Test (Unit):** `npm run test` (Vitest)
*   **Test (E2E):** `npm run test:e2e` (Playwright)
*   **Lint:** `npm run lint`

### Quiz Interface (`/quiz-mensal-interface`)
*   **Install:** `npm install`
*   **Run Dev:** `npm run dev` (Next.js, port 3001)
*   **Build:** `npm run build`
*   **Test:** `npm run test` (Jest)
*   **Lint:** `npm run lint`

## 4. Environment Setup

Each service requires its own `.env` file based on the `.env.example` provided in its respective directory.

*   **Backend:** Requires `DATABASE_URL`, `REDIS_URL`, `SECURITY_SECRET_KEY`, `SECURITY_CSRF_SECRET_KEY`, `PHI_ENCRYPTION_KEY` (base64), `ENCRYPTION_KEY_CURRENT` (Fernet), and `HASH_SALT` (hex).
*   **Frontend:** Requires `VITE_API_URL` and Firebase config.

## 5. Directory Structure Key

*   `backend-hormonia/` - API and Worker logic.
    *   `app/` - Main application code.
    *   `alembic/` - Database migrations.
*   `frontend-hormonia/` - Main dashboard/admin application.
    *   `src/` - React source.
*   `quiz-mensal-interface/` - Patient-facing quiz application.
*   `tests/` - Cross-project or integration tests (check specific subfolders).
*   `docs/` - Project documentation.

## 6. Important Notes

*   **Dependencies:** Do NOT run `npm install` in the root. Go to the specific service directory first.
*   **Python Version:** Strictly Python 3.13+.
*   **Node Version:** Node 20+.

## 7. Recent Changes (2026-01-04)

### Backend
*   **SagaOrchestrator:** Consolidated to single modular implementation (`app/orchestration/saga_orchestrator/`). Legacy file archived.
*   **Phone Normalization:** Standardized to E.164 format across all services.
*   **Quiz Security:** Added token exp/type validation, secure cookie (environment-conditional), fixed `answered_questions` increment bug.
*   **Quiz Tables:** Dropped unused tables (quiz_sessions_v2, quiz_template_versions_v2, quiz_questions, etc.).
*   **Celery Tasks:** Fixed AsyncSession usage in `send_scheduled_message`.
*   **Patient Activation:** CompletionService now properly activates patients after flow initialization.

### Frontend (quiz-mensal-interface)
*   **Empty Quiz Handling:** Added guards for empty questions array with user-friendly error state.
