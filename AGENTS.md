# Repository Guidelines

## Project Structure & Module Organization
The workspace is split by runtime: `backend-hormonia/` hosts the FastAPI service (`app/` core modules, `alembic/` migrations, `scripts/` ops helpers) and Celery workers, while `frontend-hormonia/` contains the Vite/React client (`src/`, `components/`, `tests/`). Shared automation lives in `scripts/`, and cross-cutting scenarios land in the top-level `tests/` directory (`backend/`, `unit/`, `e2e/`). Reference deployment notes and architecture diagrams in `docs/` before altering infrastructure.

## Build, Test, and Development Commands
From `backend-hormonia/`, run `make install` once, then `make dev` to start the API and `make test` or `make test-cov` for pytest with coverage. Use `make migrate` or `make migration name="add_patient_flag"` to manage Alembic migrations, and `make docker-up` when Redis/Celery services are required. Inside `frontend-hormonia/`, execute `npm install`, `npm run dev` for the UI, `npm run quality` for lint+type+test, and `npm run test:e2e` to launch Playwright suites.

## Coding Style & Naming Conventions
Python code follows Black (line length 88) with isort and flake8; keep modules snake_case and classes in CapWords. Prefer dependency-injected services under `app/services/` and mirror schema names between `models/` and `schemas/`. In the frontend, adhere to the ESLint/TypeScript config (React 19, Tailwind) with 2-space indentation, PascalCase components, and kebab-case file names under `src/components`. Run `npm run lint` or `make format` before pushing.

## Testing Guidelines
Backend tests sit in `backend-hormonia/tests` and must respect pytest discovery (`test_*.py`, `Test*` classes) plus the `--cov-fail-under=80` threshold; mark integration or Redis cases with the provided markers. Frontend unit tests live under `frontend-hormonia/tests` and run with Vitest (`npm run test`), while Playwright specs reside in `frontend-hormonia/tests/e2e`. Keep root-level scenarios in `tests/e2e` synchronized with the docker-compose services and document any required fixtures in `docs/testing.md`.

## Commit & Pull Request Guidelines
Follow the Conventional Commits pattern observed in history (`type(scope): imperative summary`), keep commits focused, and include relevant issue IDs. Before opening a PR, ensure all quality commands succeed, update screenshots for UI changes, and capture environment versions when tests run. The `.github/PULL_REQUEST_TEMPLATE.md` checklist is mandatory; fill testing sections, highlight security considerations, and describe rollout steps if migrations or feature flags are involved.

## Security & Configuration Tips
Store secrets only in `.env` files (see the provided examples) and validate them with `scripts/validate-env.py`. When touching authentication flows, run `scripts/run-auth-tests.sh` and review Firebase policies in `backend-hormonia/FIREBASE_SECURITY_README.md`. Never commit generated certificates (`backend-hormonia/certs/`) or Playwright reports; add new sensitive paths to `.gitignore`.
