# M013: Remediação de Segurança Crítica/Alta

**Vision:** Corrigir e otimizar as vulnerabilidades documentadas no relatório de segurança, começando pelos findings críticos e altos que expõem PHI/LGPD: WhatsApp sem autenticação, SSRF, IDOR/BOLA entre médicos/pacientes, serving público de uploads/reports privados e abuso de link/sessão de quiz.

## Success Criteria

- F-01 unauthenticated WhatsApp management API is no longer reachable anonymously.
- F-02 WhatsApp/WuzAPI media fetch blocks SSRF destinations before outbound requests.
- F-03 through F-11 cross-doctor/cross-patient and public-file exposure paths fail safely under tests.
- Legitimate assigned-doctor/admin/patient flows remain functional for the touched endpoints.
- A final evidence matrix maps every critical/high finding to passing verification evidence.

## Slices

- [x] **S01: S01** `risk:high` `depends:[]`
  > After this: Anonymous WhatsApp management calls are rejected, authorized mocked operations still work, and SSRF vectors against media fetch are blocked by tests.

- [x] **S02: S02** `risk:high` `depends:[]`
  > After this: Doctor A cannot access Doctor B’s messages, free-text flow responses or flow override schedules; assigned doctor/admin access still passes.

- [x] **S03: S03** `risk:high` `depends:[]`
  > After this: Quiz link creation, status/history, active links and public submit reject foreign, expired, forged or mismatched state while a legitimate fixture quiz still completes.

- [x] **S04: S04** `risk:high` `depends:[]`
  > After this: Private uploads and generated patient PDFs are not reachable through public `/uploads`; authorized gated download works in tests.

- [x] **S05: S05** `risk:high` `depends:[]`
  > After this: Direct report download/export/share/history reject cross-user or cross-doctor report IDs and preserve legitimate owner/admin behavior.

- [x] **S06: S06** `risk:medium` `depends:[]`
  > After this: A consolidated evidence matrix shows F-01..F-11 mapped to passing commands/tests and explicitly lists deferred medium/proof-gap follow-ups.

## Boundary Map

### S01 → S02

Produces:
- Authenticated WhatsApp management boundary: `/api/v2/whatsapp/*` rejects anonymous callers before service execution.
- `fetch_and_encode_media` or equivalent WuzAPI media seam enforces SSRF-safe URL validation before outbound fetch.
- SSRF test corpus for blocked schemes, private/loopback/link-local/metadata targets and redirects.

Consumes:
- Existing canonical session/user role dependencies from `app.dependencies`.

### S02 → S03

Produces:
- Shared admin-or-assigned-doctor patient ownership helper/pattern proven against messages, flow responses and flow overrides.
- Two-doctor/two-patient fixture or factory pattern for negative authorization tests.

Consumes:
- Existing Patient/User models and auth dependencies.

### S02 → S05

Produces:
- Ownership-check pattern for resource IDs that resolve through patient ownership or generated_by.
- Negative authorization fixture pattern for cross-doctor/cross-user resource IDs.

Consumes:
- Existing report models/cache/service surfaces.

### S03 → S06

Produces:
- Quiz token/session invariants: opaque or signed session state, token hash/link-state/expiration/patient binding, and rejection of raw forged session IDs.
- Tests proving valid public quiz flow still works while forged/expired/mismatched submissions fail.

Consumes:
- Shared patient access helper and two-doctor fixtures from S02.

### S04 → S05

Produces:
- Private upload/report storage boundary: private files are not served by unauthenticated `/uploads`; gated access path exists for authorized downloads.
- Generated report output no longer relies on public deterministic static paths.

Consumes:
- Existing upload metadata, report generation task and storage settings.

### S01–S05 → S06

Produces:
- Finding-level proof artifacts and focused tests for each boundary.

Consumes:
- All fixed boundaries, shared helpers and negative fixture patterns.
