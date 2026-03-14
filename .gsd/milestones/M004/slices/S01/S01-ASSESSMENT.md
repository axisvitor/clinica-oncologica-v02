---
date: 2026-03-14
triggering_slice: M004/S01
verdict: no-change
---

# Reassessment: M004/S01

## Coverage Check

- O stack local autentica a equipe, restaura sessão e carrega `/dashboard`, `/admin` e `/whatsapp` sem depender de Firebase ou de superfícies legadas no caminho oficial. → S02, S03, S04, S06
- `firebase_uid`, `/session/*`, `X-Session-ID` e fallbacks legados em escopo deixam de ser parte viva do runtime oficial ou passam a ser rejeitados/tombstonados explicitamente. → S02, S04, S05
- O frontend oficial para de depender funcionalmente de semântica/comentários de Firebase para auth/sessão. → S03, S05
- O milestone fecha com prova montada de runtime sem Firebase, não só com grep, diff e testes unitários. → S06

Coverage check passed.

## Changes Made

No changes.

S01 retirou o risco que prometia retirar: agora existe uma fronteira executável para o resíduo vivo do runtime oficial, com allowlist, verificador `--report/--check`, âncoras explícitas e regressão de subprocesso. Isso reduz incerteza, mas não desloca ownership dos slices restantes.

O roadmap continua coerente como está:
- **S02 segue sendo o próximo passo correto.** O próprio handoff de S01 concentra o maior resíduo backend em `auth_dependencies.py`, `auth_session_cache.py`, `auth_legacy_firebase.py`, `auth_session.py` e nas seams de `X-Session-ID` / bearer / `/session/*`, exatamente o corte que S02 já possui.
- **S03 continua necessário sem mudança de ordem.** S01 ainda mostra resíduo funcional/narrativo no frontend oficial; isso continua pertencendo ao slice de convergência session-first do app oficial.
- **S04 continua necessário como slice distinto.** O que S01 produziu foi um mapa e um gate, não a aposentadoria das superfícies legadas. Rejeição/tombstone explícito de `/session/*`, `X-Session-ID` e fallbacks legados continua sendo trabalho próprio depois da convergência backend/frontend.
- **S05 continua necessário como limpeza adjacente, não como substituto de S02/S03.** `firebase_uid`, cache, auditoria, tipos e docs operacionais ainda precisam ser alinhados ao runtime sem Firebase depois que o caminho feliz oficial estiver convergido.
- **S06 continua sendo o dono da prova montada final.** S01 provou guardrails e diagnóstico; ainda falta a prova integrada do stack sem Firebase nas rotas críticas.

A boundary map continua compatível com o que S01 realmente entregou: guardrails e mapa de resíduos para S02/S03/S04/S05 consumirem, sem surgir risco novo que justifique reordenar, fundir ou dividir slices.

## Requirement Coverage Impact

None.

Requirement coverage remains sound:
- **R048** e **R049** continuam com ownership crível em **S02**, agora com um mapa executável de resíduos para guiar a convergência backend sem perder o boundary oficial.
- **R050** continua corretamente ancorado em **S03**, com suporte de **S05** para remover o resíduo funcional/narrativo restante do frontend oficial.
- **R047** continua corretamente fechado por **S05**, suportado por S02–S04 e rechecado por **S06** na prova integrada final.
- A necessidade de prova viva para **R053** continua coberta por **S06**; S01 não substitui esse fechamento porque não exercita o stack montado.

Nenhuma mudança de ownership ou status é necessária em `.gsd/REQUIREMENTS.md`.

## Decision References

- "M004/S01 uses a slice-local `runtime-residue-allowlist.json` plus `verify-runtime-residue.sh` to guard official auth/session residue by category and scope; repo-wide `firebase` or `/session` bans are explicitly out of scope because they create false positives."
- "M004/S01 backs the residue guard with a subprocess-style pytest regression (`backend-hormonia/tests/unit/test_runtime_residue_guard.py`) so later slices can change the boundary intentionally without relying on manual grep checks."
- "M004/S01/T02 publishes the residue handoff with the verifier's exact category ids and `backend` / `frontend` scope names; any intentional boundary shrink must update the allowlist, research, summary, and UAT together."
- "M004/S01 pins approved runtime-residue hotspots by explicit file anchors in `runtime-residue-allowlist.json`; if a hotspot moves, the boundary must be updated intentionally instead of silently inheriting drift."
- "M004/S01 boundary shrinkage is not complete on a green script alone; `runtime-residue-allowlist.json`, `S01-RESEARCH.md`, `S01-SUMMARY.md`, and `S01-UAT.md` are one contract and must move together."
