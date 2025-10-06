# Project Overview

This is a web application called "Sistema Hormonia", an AI-powered patient communication platform for hormone therapy. It's a monorepo with a frontend, a backend, and a quiz interface.

**Frontend:**
*   **Technology:** React, TypeScript, Vite, Tailwind CSS, Radix UI, Zustand, React Query
*   **Path:** `frontend-hormonia`
*   **Key Scripts:**
    *   `npm install`: Install dependencies
    *   `npm run dev`: Start development server
    *   `npm run test`: Run tests

**Backend:**
*   **Technology:** Python, FastAPI, PostgreSQL (Supabase), Redis, Celery, Pytest
*   **Path:** `backend-hormonia`
*   **Key Scripts:**
    *   `pip install -r requirements.txt`: Install dependencies
    *   `uvicorn app.main:app --reload`: Start development server
    *   `make dev`: Start development server using make
    *   `make test`: Run tests

**Quiz Interface:**
*   **Technology:** Next.js, React, TypeScript
*   **Path:** `quiz-mensal-interface`
*   **Key Scripts:**
    *   `npm install`: Install dependencies
    *   `npm run dev`: Start development server
    *   `npm run test`: Run tests

# Building and Running

## Docker Compose (Recommended)

The easiest way to run the entire application is using Docker Compose.

```bash
docker-compose up -d
```

This will build and start the frontend and backend services.

## Individual Services

You can also run each service individually.

### Backend

```bash
cd backend-hormonia
pip install -r requirements.txt
cp .env.example .env # Edit .env with your credentials
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend-hormonia
npm install
cp .env.example .env # Edit .env with your credentials
npm run dev
```

### Quiz Interface

```bash
cd quiz-mensal-interface
npm install
npm run dev
```

# Development Conventions

*   **Backend:** The backend follows a modular architecture with a clear separation of concerns. It uses `pytest` for testing.
*   **Frontend:** The frontend uses `eslint` and `prettier` for code quality and formatting. It uses `vitest` and `playwright` for testing.
*   **Commits:** The project uses conventional commits.
