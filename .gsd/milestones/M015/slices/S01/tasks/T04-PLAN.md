---
estimated_steps: 14
estimated_files: 5
skills_used:
  - tdd
  - verify-before-complete
  - review
---

# T04: Add harness contract tests and run the S01 closure gate

Why: S01 should be regression-safe after the first successful runtime proof. Unit/contract tests catch false-green runner changes, live-provider drift, and redaction regressions without requiring Docker for every small edit, while the final closure command still exercises the real DB seam.

Expected executor skills_used frontmatter: `tdd`, `verify-before-complete`, `review`.
Estimated scope: about 7 steps / 1 new test file plus existing verification targets.

Do:
1. Add `backend-hormonia/tests/security/test_m015_runtime_harness.py` that inspects only committed source files, not `.gsd`, `.planning`, `.audits`, `.m015-runtime`, or other ignored runtime scratch.
2. Assert the runner exposes `--seam db`, rejects unknown seams, uses traps/cleanup, masks DSNs, and does not default to a false full-milestone green before S02-S05 exist.
3. Assert `scripts/security/m015-runtime/docker-compose.yml` has isolated service names, a TLS-enabled Postgres command, no `env_file: .env`, no live WuzAPI/Gemini service for S01, no production volume names, and a `db-probe` service on the compose network.
4. Assert redaction helper rejects credentialed PostgreSQL URLs, private key blocks, cookies/authorization headers, Firebase service account strings, CPF/email/phone-like values, `/mnt/c` absolute paths, and raw patient names, while accepting the expected sanitized DB evidence shape.
5. Assert the DB seam evidence schema contains required top-level rows/fields for command, migration, TLS, RLS catalog, RLS allow, RLS deny, redaction, non-goals, and teardown.
6. Run the focused pytest contract suite and then the real runtime command from the repository root.
7. If runtime reveals a selected DB seam red signal, fix it in product/harness code before marking the task complete; do not document selected DB TLS/RLS red as green.

Failure Modes (Q5): pytest detects false green/redaction drift -> contract failure; Docker runtime flakes -> runtime failure with sanitized phase; evidence schema missing rows -> test failure; selected security red signal -> implementation fix required before completion.

Load Profile (Q6): contract tests are file reads and regex/YAML parsing; runtime command remains one stack. At 10x, Docker resources break before tests; keep unit tests independent of Docker.

Negative Tests (Q7): unknown seam, unsafe evidence sentinels, live-provider compose reference, missing DB evidence row, and false default full-milestone pass are explicitly covered.

## Inputs

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/redaction.py`
- `scripts/security/m015-runtime/db_seam.py`
- `backend-hormonia/app/core/database/async_engine.py`
- `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/db-seam-summary.md`

## Expected Output

- `backend-hormonia/tests/security/test_m015_runtime_harness.py`

## Verification

cd backend-hormonia && PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py tests/security/test_m015_runtime_harness.py -q && cd .. && ./scripts/security/verify-m015-runtime-security.sh --seam db

## Observability Impact

Locks in the evidence schema and redaction contract so future runner changes surface as actionable pytest failures before they become ambiguous runtime or review failures.
