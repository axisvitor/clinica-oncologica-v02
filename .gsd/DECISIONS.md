# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? |
|---|------|-------|----------|--------|-----------|------------|
| 1 | 2026-03-14 | M004/S03/T04 | Canonical frontend admin/user contract | Drop Firebase-shaped admin/user fields (`firebase_uid`, provider-era metadata) from the official frontend/shared type surfaces and normalizers; only keep minimal routed mock cleanup when a source file still needs to satisfy the narrowed type | The shipped frontend auth path is already backend-cookie session-first, so preserving Firebase-shaped canonical fields only keeps dead semantics alive in types, mocks, and narrative surfaces | Yes — if a routed runtime consumer later proves it still needs a backend field, reintroduce it from observed usage instead of legacy inertia |
| 2 | 2026-03-14 | M004/S03/T05 | Post-cut residue publication | Keep the S01 `frontend` scopes in `runtime-residue-allowlist.json` with `approved: []` once S03 removes all official frontend residue; do not delete the scopes or rename the categories | Empty approved sets preserve the existing category/scope vocabulary and turn any frontend auth/session regression into an explicit verifier failure instead of silent drift or ad-hoc bookkeeping | Yes — if the verifier later gains a clearer first-class zero-scope representation, the encoding can change without changing the boundary meaning |
