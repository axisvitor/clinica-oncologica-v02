# Repository Guidelines

## Project Structure & Module Organization
- `backend-hormonia/app` hosts FastAPI routers, services, repositories, and models; supporting folders such as `migrations/`, `scripts/`, and `seeds/` manage database evolution and job orchestration.
- `frontend-hormonia/src` contains the React 19 client with feature modules under `components/`, `hooks/`, and `services/`; shared typings live in `types/`, while `tests/` and `test-results/` capture UI regression assets.
- `quiz-mensal-interface/app` delivers the monthly quiz (Next.js 14), with reusable pieces under `components/` and Jest specs inside `tests/`.
- Shared documentation resides in `docs/`; coverage artifacts (`htmlcov/`, `coverage/`) should be regenerated, not versioned manually.

## Build, Test, and Development Commands
- Backend: `make install`, `make dev`, and `make docker-up` prepare the API stack; `make test` / `make test-cov` run pytest (HTML reports in `backend-hormonia/htmlcov/`); use `make migrate` and `make migration name="add_feature"` for Alembic tasks.
- Frontend: from `frontend-hormonia`, run `npm install`, `npm run dev` for Vite, `npm run quality` (eslint + typecheck + Vitest CI), and `npm run test:e2e` for Playwright suites.
- Quiz app: `pnpm install`, `pnpm dev`, `pnpm test:coverage`, and `pnpm type-check`; `pnpm railway-build` matches Railway deployments.

## Coding Style & Naming Conventions
- Python follows PEP 8 with 4-space indents, strict type hints, and Google-style docstrings; format using `make format` (Black + isort) and lint with `make lint`.
- React/Next code uses TypeScript strict mode, PascalCase components, camelCase helpers, Tailwind utility classes, and domain-specific hooks via `use*` naming. Enforce style with `npm run lint`, `npm run typecheck`, and keep `eslint` warnings at zero.

## Testing Guidelines
- Maintain ≥80% coverage for backend (pytest + `pytest --cov=app`), frontend (Vitest + `npm run test:coverage`), and quiz (Jest thresholds are enforced in `package.json`). Name specs `test_*.py` or `*.spec.ts[x]`/`*.test.ts[x]` and store fixtures alongside subject modules.
- Execute Playwright smoke suites (`npm run test:e2e:smoke`) before merging UI-sensitive changes; capture failures in `test-results/` for review.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat(patients): add CPF validation`) and keep messages scoped to a logical change. Squash noisy WIP commits before pushing.
- Pull requests must reference relevant issues, list schema or environment impacts, and include test evidence (coverage links, Playwright reports). Ensure migrations accompany schema changes and that secrets stay in `.env` files documented by `.env.example`.

## Security & Configuration Tips
- Never commit `.env` contents; update `.env.example` when adding variables for WhatsApp, Firebase, Redis, or Gemini integrations.
- Validate all inbound payloads (Pydantic schemas, zod validators) and sanitize outbound HTML with DOMPurify in shared UI helpers.
- Run `docker compose logs` periodically to confirm Celery and Redis health, and prefer `make docker-down` over manual container stops to keep states consistent.
