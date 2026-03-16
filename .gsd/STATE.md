# GSD State

**Active Milestone:** M006 — Purga Final de Código Morto e Resíduo Legado
**Active Slice:** S03 — Purga final de bridges, tombstones, serviços mortos e narrativa operacional errada
**Phase:** executing
**Requirements Status:** 1 active · 25 validated · 7 deferred · 11 out of scope

## Milestone Registry
- ✅ **M001:** Bulletproof Flow Pipeline
- ✅ **M002:** First-Party Authentication Cutover
- ✅ **M003:** Structural Refactor And Dead-Code Cleanup
- ✅ **M004:** Convergência Canônica de Runtime
- ✅ **M005:** Fechamento Definitivo de Schema e Migrações
- 🔄 **M006:** Purga Final de Código Morto e Resíduo Legado

## Recent Decisions
- D42: Rename `FIREBASE_SESSION_TTL_SECONDS` → `SESSION_TTL_SECONDS` in `auth_session_contract.py`
- D43: Classify `backend-hormonia/docs/repo/**` as historical archive via `HISTORICAL-ARCHIVE.md` marker

## Blockers
- None

## Next Action
Execute T01: Stabilize proof surfaces and delete dead backend auth/session cluster.
