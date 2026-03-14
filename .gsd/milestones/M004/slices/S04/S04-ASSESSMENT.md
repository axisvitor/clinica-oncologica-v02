---
date: 2026-03-14
triggering_slice: M004/S04
verdict: no-change
---

# Reassessment: M004/S04

## Changes Made

No changes.

### Success-Criterion Coverage Check
- O stack local autentica a equipe, restaura sessão e carrega `/dashboard`, `/admin` e `/whatsapp` sem depender de Firebase ou de superfícies legadas no caminho oficial. → S05, S06
- `firebase_uid`, `/session/*`, `X-Session-ID` e fallbacks legados em escopo deixam de ser parte viva do runtime oficial ou passam a ser rejeitados/tombstonados explicitamente. → S05, S06
- O frontend oficial para de depender funcionalmente de semântica/comentários de Firebase para auth/sessão. → S06
- O milestone fecha com prova montada de runtime sem Firebase, não só com grep, diff e testes unitários. → S06

### Why the roadmap still holds
- S04 retired the risk it was supposed to retire: the official backend auth/session path is cookie-only, and root `/session/*` is an explicit tombstone instead of a live compatibility island.
- Repo evidence still matches S05's stated scope rather than revealing a new slice gap: `firebase_uid` and Firebase operational narrative remain alive in runtime-adjacent cache, audit, adapter, and docs seams such as `backend-hormonia/app/api/v2/user_cache_shared.py`, `backend-hormonia/app/services/audit_log.py`, `backend-hormonia/app/dependencies/auth_user_adapter.py`, and `backend-hormonia/app/api/v2/routers/docs/data_providers.py`.
- Nothing in S04 suggests pulling S06 earlier. The mounted no-Firebase replay is still more trustworthy after S05 shrinks the remaining runtime-adjacent residue.

## Requirement Coverage Impact

None. Requirement coverage remains sound:
- R047 is still credibly owned by S05, with S06 providing the assembled no-Firebase replay.
- R049 still has a concrete remaining owner in S05 because `firebase_uid` remains live in runtime-adjacent cache/audit/adapter seams.
- R050 remains validated from S03 and still has final assembled recheck coverage in S06.
- R053 still correctly depends on S06 for mounted proof; S04 did not surface a new blocker or ownership gap.

## Decision References

- D3
- D4
- D5
