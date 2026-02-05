# Repository Guidelines

## Project Structure & Module Organization
- `backend-hormonia/`: FastAPI backend (Python 3.13). Core code in `app/`, migrations in `alembic/`, tests in `tests/`.
- `frontend-hormonia/`: React + Vite dashboard. Source in `src/`, shared libs in `lib/`, tests in `tests/`, static assets in `public/`.
- `quiz-mensal-interface/`: Next.js quiz app. App Router in `app/`, UI in `components/`, API client in `lib/`, tests in `tests/`.
- `docs/`, `scripts/`, and top-level `tests/` host project-wide docs, utilities, and cross-cutting tests.

## Build, Test, and Development Commands
Backend (`cd backend-hormonia`)
- `python -m venv .venv && source .venv/bin/activate` - local venv
- `pip install -r requirements.txt` - install deps
- `alembic upgrade head` - migrate database
- `uvicorn app.main:app --reload --port 8000` - dev API
- `pytest` - runs tests (integration excluded by default)

Frontend (`cd frontend-hormonia`)
- `npm install`
- `npm run dev` - Vite dev server
- `npm run build` - production build
- `npm run test` - Vitest
- `npm run lint` / `npm run typecheck` - lint + TS check
- `npx playwright test -c tests/e2e/playwright.config.e2e.ts` - E2E

Quiz (`cd quiz-mensal-interface`)
- `npm install`
- `npm run dev` - Next.js dev server (port 3001)
- `npm run build` / `npm run start`
- `npm run test` - Jest
- `npm run lint`

## Coding Style & Naming Conventions
- Python: formatted with Black/Isort (line length 120); lint with Ruff. Use 4-space indent, `snake_case` for functions/modules, `PascalCase` for classes.
- TypeScript: ESLint rules in `frontend-hormonia/eslint.config.js`. Use 2-space indent, semicolons, `camelCase` for values, `PascalCase` for React components/types; avoid `any` unless justified.
- Keep filenames descriptive and colocate tests near features or in `tests/`.

## Testing Guidelines
- Backend: pytest in `backend-hormonia/tests/` with markers (e.g., `@pytest.mark.integration`). Default run skips integration (`-m "not integration"`).
- Frontend: Vitest unit/integration tests in `frontend-hormonia/tests/` and `src/**/__tests__`; Playwright E2E in `frontend-hormonia/tests/e2e`.
- Quiz: Jest tests in `quiz-mensal-interface/tests/`; coverage thresholds are enforced (branches 75%, functions/lines/statements 80%).

## Commit & Pull Request Guidelines
- Use Conventional Commits: `type(scope): message` (e.g., `fix(backend): ...`, `chore: ...`, `conductor(plan): ...`).
- PRs should include a clear summary, testing notes, and screenshots for UI changes; link related issues.

## Security, Configuration, and Agents
- Copy `.env.example` in each service; never commit secrets.
- Do not run `npm install` at the repo root; each app has its own `node_modules/`.
- If using automated agents, review `CLAUDE.md` and `GEMINI.md` for repository-specific coordination rules.
