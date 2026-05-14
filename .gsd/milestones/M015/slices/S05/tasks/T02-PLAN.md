---
estimated_steps: 8
estimated_files: 4
skills_used: []
---

# T02: Implement unified all-seam runner mode

Why: The milestone success criteria require a single committed runner that can execute all seams; S05 must convert no-filter invocation from fail-closed placeholder into all-seam closeout while preserving unknown seam fail-closed behavior.
Do:
1. Update CLI usage/listing so `--seam` is optional for all-seam closeout but still accepted for scoped debugging.
2. Add deterministic seam order: `db`, `session`, `provider`, `artifact`.
3. Ensure each seam gets its own correlation ID/evidence directory or a clear parent all-run correlation with child seam correlations.
4. Preserve `--keep-stack`, `--teardown-only`, port/project isolation, and sanitized phase logs.
5. Keep scoped seam behavior unchanged.
Done when: no-filter dry/static contracts pass and unknown seam still exits before setup.

## Inputs

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/README.md`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`

## Expected Output

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/README.md`

## Verification

bash -n scripts/security/verify-m015-runtime-security.sh && ./scripts/security/verify-m015-runtime-security.sh --list-seams && ./scripts/security/verify-m015-runtime-security.sh --seam not-a-seam >/tmp/m015-unknown.out 2>&1; test $? -eq 64 && grep -q "unknown seam" /tmp/m015-unknown.out && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_runtime_harness.py ../scripts/security/m015-runtime/tests/test_runner_contract.py -q

## Observability Impact

Adds all-run/child-seam phase labels and preserves correlation IDs for closeout diagnostics.
