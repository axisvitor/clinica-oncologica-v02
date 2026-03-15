# S01: Fechar a costura auth/session legado ainda “viva”

**Goal:** Avançar R052 tornando honesto o backend auth/session: `get_current_user()` e chokepoints adjacentes deixam de lazy-loadar bearer/Firebase legado, e os transportes antigos que ainda permanecem montados passam a existir só como rejeição/tombstone explícita.
**Demo:** Um mantenedor roda o pack focado de auth/session e vê cookie-backed staff auth, verify-session, admin/system checks e websocket continuarem verdes no contrato canônico; tentativas por `X-Session-ID`, session-as-Bearer e `session_id` em websocket recebem diagnósticos estáveis; e `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` não aprova mais hotspots backend para `firebase_uid`, `x_session_id`, `session_bearer_fallback` ou `websocket_session_id_query`.

## Must-Haves

- `get_current_user()` e wrappers adjacentes de staff auth resolvem usuário apenas pelo contrato canônico de sessão por cookie e falham fechado antes de qualquer import lazy ou fallback Firebase/bearer.
- Menções legadas que continuam montadas em `/session/*`, websocket e rejection plumbing deixam de ser “runtime residue aprovado” e passam a ser cobertas apenas por prova focada de rejeição/tombstone com diagnósticos estáveis.
- O runtime residue guard é republicado com zero approved hits para os hotspots backend de auth/session citados acima, sustentando R052 como guardrail de regressão em vez de bookkeeping de dívida.

## Proof Level

- This slice proves: contract
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependencies.py tests/unit/test_runtime_residue_guard.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_validation.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_hard_cut_cleanup.py -k "rejects_legacy_header_transport_without_cookie or stable_diagnostics"`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
- `python3 - <<'PY'
from pathlib import Path
text = Path('backend-hormonia/app/dependencies/auth_dependencies.py').read_text(encoding='utf-8')
for needle in ('authenticate_legacy_bearer_user', '_get_auth_legacy_firebase', '_get_firebase_service'):
    assert needle not in text, needle
print('legacy auth seam retired')
PY`

## Observability / Diagnostics

- Runtime signals: respostas HTTP com `detail`/`message`/`error`/`request_id`, erros websocket `AUTH_WEBSOCKET_SESSION_INVALID` com `session_source`, e warnings explícitos quando um transporte legado é rejeitado.
- Inspection surfaces: os packs focados de pytest acima, `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`, e a checagem estática publicada para `auth_dependencies.py`.
- Failure visibility: uma regressão localiza rapidamente se o problema está no chokepoint HTTP, na wrapper admin, na rejeição websocket/root tombstone, ou na própria republicação do guard de resíduo.
- Redaction constraints: não publicar session IDs reais, tokens ou credenciais; manter apenas fixtures mascaradas e diagnósticos sem segredo.

## Integration Closure

- Upstream surfaces consumed: `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, `backend-hormonia/app/api/websockets.py`, `backend-hormonia/app/routers/auth_session.py`.
- New wiring introduced in this slice: none
- What remains before the milestone is truly usable end-to-end: S02 ainda remove o resíduo Firebase estrutural de `users`; S03 ainda purga bridges/tombstones/docs/workflows repo-wide fora deste seam backend.

## Tasks

- [x] **T01: Cortar o fallback bearer/Firebase dos chokepoints de staff auth** `est:2h`
  - Why: o único seam ainda “vivo” é `get_current_user()` lazy-loadando compatibilidade Firebase/bearer; enquanto isso existir, o contrato cookie-only continua parcialmente fictício e pode até disparar um import legado quebrado em runtime.
  - Files: `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, `backend-hormonia/tests/unit/test_auth_dependencies.py`, `backend-hormonia/tests/api/v2/test_auth_session_priority.py`, `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`, `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`
  - Do: remover de `get_current_user()` os helpers/imports/docstrings de dual-auth e fazer o chokepoint delegar apenas ao fluxo session-first; manter `request.state` e a precedence cookie-first intactos; garantir que a wrapper admin e quaisquer bypasses de teste só caiam em fallback quando não houve tentativa de auth nenhuma, nunca quando houve header/bearer legado que deve falhar fechado; estender os testes focados para provar rejeição estável e ausência de dependência de config Firebase para staff auth.
  - Verify: `cd backend-hormonia && pytest -q tests/unit/test_auth_dependencies.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_auth_hard_cut_end_to_end.py`
  - Done when: nenhum caminho de staff auth em `auth_dependencies.py` importa ou chama o seam legado Firebase/bearer, pedidos cookie-backed continuam autorizando, e tentativas header/bearer-only falham com o contrato de 401 esperado.
- [x] **T02: Republicar o guard de resíduo com zero-approved no backend auth/session** `est:90m`
  - Why: S01 não fecha se o seam só sair do código e continuar “documentado como permitido” no allowlist; o guard precisa passar a tratar qualquer reintrodução como drift real e deixar a rejeição/tombstone explícita sob prova focada.
  - Files: `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`, `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`, `backend-hormonia/tests/unit/test_runtime_residue_guard.py`, `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`, `backend-hormonia/tests/auth/test_session_validation.py`, `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`, `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`
  - Do: republicar os scopes backend do runtime residue guard para que `firebase_uid`, `x_session_id`, `session_bearer_fallback` e `websocket_session_id_query` tenham zero approved hits nas superfícies live de auth/session; mover qualquer menção sobrevivente para fora do guard apenas quando ela estiver coberta por prova explícita de rejeição/tombstone; ajustar o teste do próprio guard se a modelagem de scope/exclude mudar; reforçar os testes focados de websocket, `/session/*`, auth/admin/system para carregar a fronteira que saiu do allowlist.
  - Verify: `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_validation.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py && cd .. && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
  - Done when: o check backend do guard fica verde sem approved hotspots para as quatro categorias, e o que restar montado como legado é provado apenas por testes de rejeição/tombstone com diagnósticos estáveis.

## Files Likely Touched

- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/dependencies/auth_session_contract.py`
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py`
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`
- `backend-hormonia/tests/unit/test_auth_dependencies.py`
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py`
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`
- `backend-hormonia/tests/auth/test_session_validation.py`
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`
