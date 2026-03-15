---
estimated_steps: 4
estimated_files: 7
---

# T01: Cortar o fallback bearer/Firebase dos chokepoints de staff auth

**Slice:** S01 — Fechar a costura auth/session legado ainda “viva”
**Milestone:** M006

## Description

O coração do slice é matar o último seam que ainda age como compatibilidade “viva”: `get_current_user()` lazy-loada o caminho legado Firebase/bearer quando falta cookie, o que deixa o contrato cookie-only incompleto e ainda depende de uma ilha legada que já não deveria participar do runtime staff-auth. Este task fecha esse seam no chokepoint HTTP e na wrapper admin, preservando o contrato canônico de sessão, a precedence cookie-first e os diagnósticos estáveis que o resto do milestone vai consumir.

## Steps

1. Remover de `backend-hormonia/app/dependencies/auth_dependencies.py` o fallback lazy de Firebase/bearer em `get_current_user()`, junto com helpers/imports/narrativa dual-auth que só existiam para esse caminho, mantendo `request.state` e o objeto de usuário resultante compatíveis com o contrato session-first.
2. Ajustar `backend-hormonia/app/api/v2/routers/admin/dependencies.py` para que header/bearer legados contem como tentativa de auth que deve falhar fechado via dependency session-first, sem cair no bypass de teste destinado apenas ao cenário sem tentativa nenhuma.
3. Estender os testes focados de unidade/API/integração para cobrir: cookie-first precedence sobre header/bearer mistos, rejeição determinística de header/bearer sem cookie, e ausência de dependência de configuração Firebase no caminho oficial de staff auth/admin/system.
4. Rodar o pack focado do task e confirmar que nenhuma rota staff-auth ainda precisa do seam legado para autenticar ou para falhar de forma inspecionável.

## Must-Haves

- [ ] `get_current_user()` não lazy-importa mais `auth_legacy_firebase` nem aceita bearer-only staff auth; o caminho oficial passa sempre pelo contrato session-first.
- [ ] Header/bearer sem cookie falha com 401 estável, enquanto cookie-backed e cookie+legacy mistos preservam o comportamento canônico e não acionam bypasses indevidos em admin/test mode.

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependencies.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `python3 - <<'PY'
from pathlib import Path
text = Path('backend-hormonia/app/dependencies/auth_dependencies.py').read_text(encoding='utf-8')
for needle in ('authenticate_legacy_bearer_user', '_get_auth_legacy_firebase', '_get_firebase_service'):
    assert needle not in text, needle
print('legacy auth seam retired')
PY`

## Observability Impact

- Signals added/changed: respostas HTTP continuam expondo `detail`/`message`/`error`/`request_id`, e os warnings de transporte legado rejeitado passam a apontar só para rejeição explícita em vez de mascarar um fallback vivo.
- How a future agent inspects this: pelo pack focado de pytest do task, pela checagem estática em `auth_dependencies.py` e pelos próprios payloads de 401/asserts nomeados em auth/admin/system.
- Failure state exposed: fica claro se a regressão é um import legado ainda vivo, um bypass admin indevido, ou um transporte header/bearer que voltou a autenticar quando deveria falhar.

## Inputs

- `backend-hormonia/app/dependencies/auth_dependencies.py` — contém o chokepoint `get_current_user()` ainda com lazy fallback Firebase/bearer.
- `backend-hormonia/app/dependencies/auth_session_contract.py` — já materializa o contrato cookie-only e serve como base do corte em vez de reimplementar a lógica.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — hoje ainda precisa distinguir “sem auth attempt” de “tentativa legada rejeitável” para não esconder regressões em teste.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — já prova o fluxo integrado session-first e a rejeição header-only em `/verify-session`; deve continuar sendo o oráculo de integração do task.

## Expected Output

- `backend-hormonia/app/dependencies/auth_dependencies.py` — chokepoint staff-auth sem lazy fallback Firebase/bearer e sem helpers mortos associados.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — wrapper admin falhando fechado quando há tentativa legada sem cookie, sem mascarar o problema com bypasses de teste.
- `backend-hormonia/tests/unit/test_auth_dependencies.py` — asserts focados para ausência do seam legado e manutenção do contrato cookie-first.
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` — provas HTTP focadas de rejeição estável e de ausência de dependência Firebase no caminho oficial.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — prova integrada continuando verde com o seam legado aposentado.
