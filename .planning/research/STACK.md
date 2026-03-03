# Stack Research

**Domain:** Frontend quality overhaul (React 19 + Vite + Next.js 14) + Google ADK integration (Python 3.13)
**Researched:** 2026-03-03
**Confidence:** HIGH (OTel/ADK conflict verified from pyproject.toml), HIGH (frontend tooling — packages verified from existing package.json), MEDIUM (ADK integration scope — pending real install test)

---

## Executive Verdict: What to Add, Remove, or Change

| Component | Status | Action | Rationale |
|-----------|--------|--------|-----------|
| `opentelemetry-api>=1.28.0,<2.0.0` | REMOVE | Delete all 9 OTel lines from requirements.txt | ADK 1.26 requires `opentelemetry-api>=1.36.0,<1.39.0`; current `<2.0.0` upper bound is compatible on version but the instrumentation packages are the blocker |
| `opentelemetry-sdk` | REMOVE | Part of OTel removal | ADK brings its own managed OTel SDK |
| `opentelemetry-instrumentation-fastapi` | REMOVE | Part of OTel removal | ADK manages its own tracing context; external FastAPI OTel causes context detachment errors |
| `opentelemetry-instrumentation-sqlalchemy` | REMOVE | Part of OTel removal | Conflicts with ADK's internal OTel context management |
| `opentelemetry-instrumentation-redis` | REMOVE | Part of OTel removal | Same context conflict |
| `opentelemetry-instrumentation-httpx` | REMOVE | Part of OTel removal | Same context conflict |
| `opentelemetry-exporter-otlp` | REMOVE | Part of OTel removal | ADK handles its own exporting |
| `opentelemetry-exporter-otlp-proto-http` | REMOVE | Part of OTel removal | Replaced by ADK's built-in OTLP |
| `opentelemetry-proto` | REMOVE | Part of OTel removal | Transitive; no longer needed directly |
| `app/core/tracing.py` | TOMBSTONE | Convert to `raise ImportError` stub | Already has graceful `OPENTELEMETRY_AVAILABLE = False` fallback; safe to remove OTel |
| `google-adk>=1.26.0,<2.0.0` | ADD | New Python package | Core ADK runtime for agent orchestration |
| `prettier>=3.5.0` | ADD (admin + quiz) | Formatter — missing from both frontends | ESLint does not enforce formatting; without Prettier, code style drifts silently |
| `eslint-config-prettier>=9.1.0` | ADD (admin + quiz) | Disables ESLint rules that conflict with Prettier | Required companion whenever Prettier is added to an ESLint project |
| `eslint-plugin-prettier>=5.x` | ADD (admin + quiz) | Surfaces Prettier violations as ESLint errors | Integrates Prettier into the existing ESLint 9 flat config |
| `eslint-plugin-jsx-a11y>=6.10.0` | ADD (admin) | Accessibility lint rules | Currently zero a11y enforcement; oncology patient-facing data demands accessible UI |
| `eslint-plugin-react-compiler` | CONSIDER | React Compiler lint rules | Admin app uses React 19; compiler rules catch optimization violations. Skip for now unless compiler is explicitly enabled |
| Prettier config | ADD | `.prettierrc` file in both frontends | Establishes canonical formatting rules |
| `identity-obj-proxy` | ADD (quiz only) | CSS module mock for Jest | Already referenced in quiz `jest.config` but missing from `devDependencies` |
| Next.js upgrade (quiz) | EVALUATE | `next@^14.2.35` → `next@^15` | Next.js 15 supports ESLint 9 flat config natively; quiz currently on eslint 8 + legacy `.eslintrc.json`; migration to flat config requires Next.js 15 |
| `msw` (quiz) | UPDATE | `^1.3.5` → `^2.x` | MSW v1 is outdated; v2 has breaking API changes but is the current standard and works with ESM |

---

## The OTel/ADK Conflict: Root Cause

Google ADK 1.26 bundles its own OpenTelemetry instrumentation and manages the OTel context internally using Python's `contextvars`. The ADK tracer creates context spans that must be detached within the same context they were attached. When external OTel instrumentation (e.g., `opentelemetry-instrumentation-fastapi`) attaches its own spans to the same `contextvars` context tree, the ADK's detach operations fail with:

```
ERROR:opentelemetry.context:Failed to detach context
```

This is not a version mismatch — it is a design conflict. ADK's internal OTel is not an optional feature; it cannot be disabled via a public API (tracked in google/adk-python#2792). The resolution is to remove all external OTel instrumentation packages and let ADK own the tracing layer entirely.

**What ADK requires (from pyproject.toml, current as of 1.26):**
- `opentelemetry-api>=1.36.0,<1.39.0`
- `opentelemetry-sdk>=1.36.0,<1.39.0`
- `opentelemetry-exporter-otlp-proto-http>=1.36.0`
- `google-genai>=1.56.0,<2.0.0` (compatible with existing `pydantic-ai-slim[google]`)
- `pydantic>=2.12.0,<3.0.0` (compatible with existing `>=2.12.5`)

**What is already installed and stays:**
- `sentry-sdk[fastapi]>=1.38.0` — Sentry remains as the error tracking layer. Sentry uses its own transport, not OTel, for error capture. The existing `monitoring_config.py` + `sentry.py` setup is unaffected by removing OTel.
- `prometheus-client>=0.24.1` — Celery/application metrics via prometheus-client are independent of OTel.
- `structlog>=24.1.0` — Structured logging is independent of OTel.

**The tracing.py situation:** `app/core/tracing.py` already has a `try/except ImportError` guard with `OPENTELEMETRY_AVAILABLE = False` fallback. Once OTel packages are removed, it gracefully degrades to `MockTracer`. Convert the file to a tombstone with `raise ImportError` to prevent any future accidental re-import.

---

## Frontend Admin (frontend-hormonia/) — Current State Assessment

**What exists and works:**
- ESLint 9 with flat config (`eslint.config.js`) — already configured correctly
- `typescript-eslint v8.45.0` — current
- `eslint-plugin-react-hooks v5.1.0` — current
- `eslint-plugin-react-refresh v0.4.23` — current
- `vitest v3.2.4` — current; test runner and coverage already configured in `vite.config.ts`
- `husky v9.1.7` + `lint-staged v16.2.4` — pre-commit hook runs `npx lint-staged`
- TypeScript strict mode enabled (`noImplicitAny`, `noImplicitReturns`, `noUncheckedIndexedAccess`)

**What is missing:**
- No `prettier` or `.prettierrc` — formatting is not enforced
- No `eslint-config-prettier` — ESLint formatting rules may conflict with any future Prettier setup
- No accessibility plugin (`eslint-plugin-jsx-a11y`) — zero a11y enforcement

**ESLint rule gaps in existing config:**
- `'no-console': 'warn'` is set but `console.log` calls left in production code are common dead code
- `@typescript-eslint/no-explicit-any: 'warn'` is a warning, not error — any-typed code drifts without enforcement

---

## Frontend Quiz (quiz-mensal-interface/) — Current State Assessment

**What exists:**
- Next.js 14.2.35 with App Router
- ESLint 8.57.0 with legacy `.eslintrc.json` (`{"extends": "next/core-web-vitals"}`) — old format
- Jest 29 + ts-jest — testing works but is split from the admin app's Vitest setup
- TypeScript 5.9.2 strict mode enabled
- Tailwind CSS v4 (via `@tailwindcss/postcss`)

**Critical gaps:**
- ESLint 8 (legacy format) vs admin app's ESLint 9 (flat config) — inconsistent lint toolchain across the monorepo
- No Prettier
- `msw v1.3.5` in test dependencies — MSW v1 is end-of-life; v2 has breaking API changes (handlers must use `http.get()` not `rest.get()`)
- `@testing-library/react v14.1.2` — this is the React 18 version; quiz app uses React 18, so this is correct, but inconsistent with admin app's `@testing-library/react v16.x` (React 19 version)
- `identity-obj-proxy` referenced in jest config's `moduleNameMapper` but not listed in `devDependencies`

**Next.js 14 vs 15 for ESLint 9:**
Next.js 15 adds native ESLint 9 flat config support. If the quiz is upgraded to Next.js 15, the `.eslintrc.json` can be migrated to `eslint.config.mjs` using `nextPlugin.flatConfig.coreWebVitals`. This aligns the quiz app with the admin app's ESLint 9 setup. **Recommendation: Upgrade Next.js to 15.x as part of this milestone.** React 18 → React 19 upgrade for the quiz app is out of scope (different testing library versions, potential breaking changes).

---

## Recommended Stack

### Core Technologies (additions/changes for v1.7)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `google-adk` | `>=1.26.0,<2.0.0` | Google Agent Development Kit | Provides Runner, Session, Agent orchestration primitives; sits alongside existing Pydantic AI agents (they use different abstraction layers — ADK is for multi-step agent orchestration, Pydantic AI is for typed structured AI calls) |
| `prettier` | `>=3.5.0` | Code formatter for both frontends | Opinionated formatter; zero config conflicts; integrates with ESLint via eslint-plugin-prettier; replaces manual formatting debate |
| `next` (quiz) | `^15.3.0` | Next.js upgrade | Unlocks ESLint 9 flat config support; App Router stability improvements |

### Supporting Libraries (frontend additions)

| Library | Version | Purpose | Which App |
|---------|---------|---------|-----------|
| `eslint-config-prettier` | `^9.1.0` | Disables ESLint formatting rules that conflict with Prettier | Both |
| `eslint-plugin-prettier` | `^5.2.0` | Surfaces Prettier violations as ESLint errors in flat config | Both |
| `eslint-plugin-jsx-a11y` | `^6.10.0` | Accessibility lint rules for JSX | Admin (frontend-hormonia) |
| `identity-obj-proxy` | `^3.0.0` | CSS module mock for Jest | Quiz only (already used but missing from deps) |

### Development Tools (no new tools — leverage existing)

| Tool | Purpose | Current State |
|------|---------|---------------|
| `vitest v3.2.4` | Test runner for admin app | Already configured in vite.config.ts |
| `husky v9.1.7` | Git hooks | Pre-commit runs lint-staged; add typecheck |
| `lint-staged v16.2.4` | Staged file linting | Add `prettier --write` to staged file action |
| `typescript-eslint v8.45.0` | TypeScript lint rules | Already configured in flat config |

---

## Installation

### Backend (Python) — OTel removal + ADK addition

```bash
# 1. Remove these 9 lines from backend-hormonia/requirements.txt:
#    opentelemetry-api>=1.28.0,<2.0.0
#    opentelemetry-sdk>=1.28.0,<2.0.0
#    opentelemetry-instrumentation-fastapi>=0.49b0,<1.0.0
#    opentelemetry-instrumentation-sqlalchemy>=0.49b0,<1.0.0
#    opentelemetry-instrumentation-redis>=0.49b0,<1.0.0
#    opentelemetry-instrumentation-httpx>=0.49b0,<1.0.0
#    opentelemetry-exporter-otlp>=1.28.0,<2.0.0
#    opentelemetry-exporter-otlp-proto-http>=1.28.0,<2.0.0
#    opentelemetry-proto>=1.28.0,<2.0.0

# 2. Add google-adk to requirements.txt:
# google-adk>=1.26.0,<2.0.0

# 3. Install (in Railway/local backend env):
pip install -r requirements.txt
```

### Admin Frontend (frontend-hormonia/)

```bash
cd frontend-hormonia

# Add Prettier + ESLint integration
npm install -D prettier@^3.5.0 eslint-config-prettier@^9.1.0 eslint-plugin-prettier@^5.2.0

# Add accessibility linting
npm install -D eslint-plugin-jsx-a11y@^6.10.0
```

### Quiz Frontend (quiz-mensal-interface/)

```bash
cd quiz-mensal-interface

# Next.js upgrade
npm install next@^15.3.0

# Add Prettier + ESLint integration
npm install -D prettier@^3.5.0 eslint-config-prettier@^9.1.0 eslint-plugin-prettier@^5.2.0

# Fix missing test dep
npm install -D identity-obj-proxy@^3.0.0

# Optional: MSW v2 upgrade (breaking API change — separate task)
# npm install -D msw@^2.7.0
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|------------------------|
| Remove all OTel packages | Upgrade OTel to match ADK range (>=1.36.0,<1.39.0) | Only if you need OTel instrumentation of FastAPI/SQLAlchemy/Redis AND are willing to manage dual-OTel context between ADK and external instrumentation. The context detachment error (adk-python#1670) is a known bug with no fix. Do not use. |
| `google-adk>=1.26.0,<2.0.0` | Remain on Pydantic AI only, no ADK | Valid choice if ADK features (Runner, multi-step orchestration, Session management) are not needed. Current Pydantic AI agents handle 4 typed operations — if that scope doesn't expand, ADK is unnecessary. |
| Prettier | Biome | Biome is faster (Rust-based) and handles both lint + format, but has gaps in ESLint plugin ecosystem (e.g., `eslint-plugin-react-compiler` works in ESLint but not Biome). Given existing ESLint 9 investment in both frontends, Prettier alongside ESLint is lower friction. |
| Next.js 15 upgrade (quiz) | Keep Next.js 14, keep ESLint 8 | Valid if the quiz frontend is not being heavily modified. However, ESLint 8 is EOL. The quiz needs lint fixes regardless, so upgrading Next.js to unlock ESLint 9 flat config is the cleaner path. |
| `eslint-plugin-jsx-a11y` (admin) | Manual a11y audit | Manual audits catch real issues but don't enforce anything in CI. For healthcare data shown to oncology patients, automated a11y lint is the minimum viable enforcement. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `opentelemetry-instrumentation-fastapi` alongside ADK | Context detachment errors — ADK's internal OTel spans are created in one `contextvars` context and the external instrumentor detaches them in a different one, causing `Failed to detach context` runtime errors | Remove OTel instrumentation entirely; ADK owns the tracing layer |
| `opentelemetry-api>=1.28.0` + ADK together | ADK 1.26 requires `>=1.36.0,<1.39.0`; even if pip resolves to 1.36.x, the instrumentation context conflict above still applies | Remove all external OTel packages |
| Upgrading quiz to React 19 in this milestone | `@testing-library/react` v14 (current in quiz) is for React 18; v16 is for React 19. Upgrading React requires upgrading testing-library, which may break existing tests. Out of scope for a quality review milestone. | Keep quiz on React 18; only admin uses React 19 |
| `eslint-disable` comments as dead code cleanup | Suppressing lint errors is not removing dead code. Dead code removal means deleting unused components, routes, and API calls. | Delete unreachable code paths, unused imports, and untriggered routes |
| MSW v1 for new quiz tests | MSW v1 (`rest.get()`) is end-of-life; v2 API is breaking (`http.get()` + `HttpResponse`). New tests written against v1 will need to be rewritten. | Either upgrade to MSW v2 in a dedicated task, or avoid writing new MSW-dependent tests until the upgrade is done |
| Prettier as an ESLint rule with `--fix` in CI | Running `eslint --fix` with Prettier rules in CI will auto-modify source code and cause CI to fail with diff. | Run `prettier --check` in CI (read-only); run `prettier --write` in pre-commit via lint-staged |

---

## Stack Patterns by Variant

**If google-adk is used for multi-agent orchestration (orchestrating the 4 Pydantic AI agents):**
- Use `adk.Agent` as the orchestrator shell; keep Pydantic AI agents as the typed leaf-node tools
- ADK's `Runner` manages conversation state and tool dispatch; Pydantic AI handles the structured AI call within each tool
- Session persistence goes through ADK's `SessionService` (not a new concept — it wraps a DB backend)

**If google-adk is used only for its utilities (tools, sessions) without replacing Pydantic AI:**
- Import `google.adk` selectively (e.g., `from google.adk.sessions import InMemorySessionService`)
- Do NOT replace `PIISafeAgent` — the LGPD PII redaction wrapper is a compliance requirement enforced by CI lint; ADK has no equivalent

**If Next.js upgrade causes quiz build failures:**
- Next.js 15 has App Router as default; if quiz uses Pages Router, check for deprecated APIs
- Run `next build` after upgrade; review deprecation warnings before fixing lint

**If ADK's internal OTel generates too much tracing noise:**
- Set `GOOGLE_GENAI_USE_VERTEXAI=false` and do not configure GCP exporters; ADK's OTel will still trace but export nowhere
- For future observability, configure the ADK OTLP exporter to point to a Jaeger or similar collector

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `google-adk>=1.26.0` | `pydantic>=2.12.5,<3.0.0` | ADK requires `pydantic>=2.12.0`; existing constraint `>=2.12.5` satisfies this |
| `google-adk>=1.26.0` | `google-genai>=1.56.0` | ADK requires `google-genai>=1.56.0,<2.0.0`; verify existing `pydantic-ai-slim[google]` does not pin `google-genai` below 1.56.0 |
| `google-adk>=1.26.0` | `opentelemetry-api>=1.36.0,<1.39.0` | ADK brings this as its own dependency; do not also install external instrumentation packages |
| `prettier@^3.5` | `eslint@^9.17.0` (admin) | Requires `eslint-config-prettier@^9` to disable conflicting ESLint rules; compatible with flat config |
| `prettier@^3.5` | `eslint@^8.57.0` (quiz/current) | Works with ESLint 8 + `.eslintrc.json`; but if quiz upgrades to Next.js 15 + ESLint 9, use flat config pattern |
| `next@^15.3` | `react@^18` | Next.js 15 supports both React 18 and 19; quiz stays on React 18 |
| `next@^15.3` | `eslint@^9` | Next.js 15 exports `nextPlugin.flatConfig.coreWebVitals` for flat config |
| `vitest@^3.2.4` | `@testing-library/react@^16` (admin) | React 19 testing; admin app already has correct version |
| `@testing-library/react@^14` | `react@^18` (quiz) | React 18 testing; keep at v14 for quiz, do not upgrade to v16 |

---

## OTel Package Removal Checklist

These are the exact lines to remove from `backend-hormonia/requirements.txt`:

```
# Lines to DELETE (9 total):
opentelemetry-api>=1.28.0,<2.0.0
opentelemetry-sdk>=1.28.0,<2.0.0
opentelemetry-instrumentation-fastapi>=0.49b0,<1.0.0
opentelemetry-instrumentation-sqlalchemy>=0.49b0,<1.0.0
opentelemetry-instrumentation-redis>=0.49b0,<1.0.0
opentelemetry-instrumentation-httpx>=0.49b0,<1.0.0
opentelemetry-exporter-otlp>=1.28.0,<2.0.0
opentelemetry-exporter-otlp-proto-http>=1.28.0,<2.0.0
opentelemetry-proto>=1.28.0,<2.0.0
```

Files that import OTel and need updating/tombstoning:

| File | Current Import | Action |
|------|---------------|--------|
| `app/core/tracing.py` | `from opentelemetry import trace as otel_trace` (try/except guarded) | Tombstone: `raise ImportError("OTel removed in v1.7 — tracing delegated to Google ADK")` |
| Any callers of `setup_tracing()` / `get_tracer()` | Via `from app.core.tracing import ...` | Find with Grep, replace with Sentry's `sentry_sdk.start_transaction()` or no-op |

`app/core/monitoring_config.py` does NOT import OTel — it only uses `sentry_sdk`. Safe to keep as-is.

---

## ADK Integration Points

Google ADK introduces new concepts. How they map to the existing codebase:

| ADK Concept | What It Provides | Existing Equivalent | Integration Strategy |
|-------------|------------------|--------------------|--------------------|
| `adk.Agent` | Agent definition with model + tools + instruction | `PIISafeAgent` wrapping Pydantic AI agents | ADK Agent can call Pydantic AI tools as `FunctionTool`; keep `PIISafeAgent` as the PII boundary |
| `adk.Runner` | Orchestrates multi-step agent execution | `_flow_functions.py` async orchestration | Use Runner for new multi-step workflows; keep existing flow functions for existing patient flows |
| `SessionService` | Tracks conversation state across turns | Dragonfly (Redis) session cache | ADK `InMemorySessionService` for development; custom `RedisSessionService` wrapping `RedisManager` for production |
| ADK OTel | Built-in distributed tracing | `app/core/tracing.py` (being tombstoned) | ADK traces via its own `TracerProvider`; configure OTLP exporter if needed |

---

## Sources

- `google/adk-python` `pyproject.toml` (main branch, fetched 2026-03-03) — exact OTel version constraints `>=1.36.0,<1.39.0`: https://github.com/google/adk-python/blob/main/pyproject.toml (HIGH confidence)
- `google-adk` PyPI page — v1.26.0, Python >=3.10: https://pypi.org/project/google-adk/ (HIGH confidence)
- `google/adk-python` issue #1670 — "Failed to detach context" OTel conflict: https://github.com/google/adk-python/issues/1670 (HIGH confidence — confirmed runtime behavior)
- `google/adk-python` issue #2792 — No public API to disable ADK's internal OTel: https://github.com/google/adk-python/issues/2792 (HIGH confidence — confirmed design constraint)
- `frontend-hormonia/package.json` — ESLint 9, vitest 3.2.4, husky 9.1.7, no Prettier: codebase analysis (HIGH confidence)
- `quiz-mensal-interface/package.json` — Next.js 14, ESLint 8 legacy config, msw v1, missing identity-obj-proxy: codebase analysis (HIGH confidence)
- `frontend-hormonia/eslint.config.js` — flat config already configured, no a11y rules: codebase analysis (HIGH confidence)
- `frontend-hormonia/vite.config.ts` — vitest inline config, build targets, dev proxy: codebase analysis (HIGH confidence)
- Next.js ESLint 9 support — available in Next.js 15 RC 2+: https://github.com/vercel/next.js/discussions/54238 (MEDIUM confidence — from GitHub discussion thread)
- Prettier 3.x + ESLint 9 flat config setup guide (Oct 2025): https://leandroaps.medium.com/setting-up-eslint-and-prettier-in-a-react-19-project-with-vite-using-eslint-9-326147501971 (MEDIUM confidence — community source, pattern well-established)
- ADK Sessions documentation: https://google.github.io/adk-docs/sessions/session/ (MEDIUM confidence — official docs fetched indirectly)

---

*Stack research for: Frontend quality overhaul + Google ADK integration (v1.7 milestone)*
*Researched: 2026-03-03*
*Confidence: HIGH for OTel/ADK conflict and exact packages to remove; HIGH for frontend tooling gaps; MEDIUM for ADK integration scope (real install test needed to confirm google-genai version transitive resolution)*
