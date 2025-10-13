# Repository Guidelines

## Project Structure & Module Organization
- Backend lives in `backend-hormonia/` with FastAPI app code under `app/`, data access in `sql/`, background workers in `worker/`, and Alembic migrations in `alembic/` plus legacy `migrations/`.
- Frontend lives in `frontend-hormonia/` (Vite + React). Core UI is under `src/`, reusable pieces under `components/`, and hooks/contexts colocated with their usage.
- Shared automation scripts sit in `scripts/` (see `test-setup.sh`, `run-auth-tests.sh`). Cross-cutting scenarios and performance suites reside in `tests/`.
- Playbooks, RFCs, and operational docs are under `docs/`; review relevant guidance before large structural or contract changes.

## Build, Test, and Development Commands
- Backend: run `make install` for dependencies, `make dev` to start the API on `http://localhost:8000`, and `make test` or `make test-cov` for pytest (HTML coverage with the latter). Use `make migrate` to apply Alembic upgrades.
- Frontend: from `frontend-hormonia/`, execute `npm install`, `npm run dev` for Vite hot reload, and `npm run build` for production bundles. Use `npm run test`, `npm run test:coverage`, and `npm run test:e2e` (Playwright).
- End-to-end: launch `python tests/test_runner.py` after backend or contract-impacting changes; run `scripts/run-auth-tests.sh` to verify auth flows across services.

## Coding Style & Naming Conventions
- Python follows PEP 8 with four-space indents. Format using `make format` (`black` + `isort`) and lint via `make lint` (`flake8`).
- TypeScript React code uses ESLint and Tailwind conventions; prefer PascalCase for components/contexts, `useCamelCase` for hooks, and snake_case module names in the backend.
- Alembic revisions should be timestamp-prefixed to match existing files; colocate tests beside their targets when practical.

## Testing Guidelines
- Maintain coverage at or above the baseline tracked in `coverage.lcov`. Name backend tests `test_<behavior>` and place API flows in `backend-hormonia/tests/integration/`.
- Frontend unit tests live next to components; tag Playwright specs with `@smoke` for critical coverage. Share performance and cross-service tests through `tests/`.
- Extend existing pytest fixtures instead of duplicating setup; document new fixtures in `docs/` if they alter global state.

## Commit & Pull Request Guidelines
- Mirror the repository history: use capitalized prefixes such as `Fix:`, `docs:`, or celebratory release markers. Keep subject lines imperative and concise.
- Pull requests should outline scope, impacted modules, environment variable updates, and attach relevant logs, screenshots, or curl traces.
- Confirm local runs of lint, unit, coverage, and E2E commands before requesting review, and reference tickets or incidents in the description when applicable.

## Security & Configuration Tips
- Duplicate `.env.example` files into `.env` for local work; never commit secrets or private keys (store certificates only under `backend-hormonia/certs/`).
- Use `scripts/update-railway-vars.ps1` to sync deployment settings, and update `docs/` playbooks plus `monitoring/` rules when integrating third-party services.
