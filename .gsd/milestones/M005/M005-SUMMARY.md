---
id: M005
provides:
  - Settings-free Alembic operability, explicit Firebase historical boundaries, canonical head convergence, and mounted backend proof on the final schema.
key_decisions:
  - Keep the Alembic control plane self-contained and independent from app runtime secrets or package-import side effects.
  - Preserve any Firebase-era residue only behind explicit historical boundaries instead of leaving it in the canonical live schema contract.
  - Close the milestone with one serial final-schema proof runner that reuses the published mounted-backend contract from M004/S06.
patterns_established:
  - Prove migration operability with scrubbed-env Alembic commands plus real-Postgres replay instead of trusting imports or static graph inspection.
  - Republish live schema contracts under canonical storage first, then quarantine or archive legacy Firebase-shaped residue explicitly.
  - Verify final convergence in layers: canonical_head -> pytest_replay -> mounted_backend -> live_auth_probe.
observability_surfaces:
  - "cd backend-hormonia && env -i PATH=\"$PATH\" HOME=\"$HOME\" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini history"
  - "cd backend-hormonia && env -i PATH=\"$PATH\" HOME=\"$HOME\" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini heads"
  - "cd backend-hormonia && env -i PATH=\"$PATH\" HOME=\"$HOME\" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini current"
  - "cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py tests/migrations/test_canonical_schema_head_convergence.py"
  - "bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh"
  - "bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing"
  - "/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/status.json"
requirement_outcomes:
  - id: R051
    from_status: active
    to_status: validated
    proof: S03 proved in real Postgres that `base -> head` and `m005_s02_t01_publish_firebase_history_boundary -> head` converge on `m005_s03_t02_align_audit_history_head`, with canonical `users`, enum-backed `audit_logs`, and explicit historical-only `firebase_sync_history`.
  - id: R053
    from_status: active
    to_status: validated
    proof: S04 replayed both `fresh` and `existing` histories through focused post-M004 pytest packs and a mounted uvicorn backend on the canonical head, reusing the M004/S06 mounted-proof contract.
duration: ~12h55m
verification_result: passed
completed_at: 2026-03-15T13:55:14-03:00
---

# M005: Fechamento Definitivo de Schema e Migrações

**Alembic agora percorre o grafo sem segredos da app, o resíduo Firebase ficou isolado como histórico explícito, e banco novo, banco existente e backend montado convergem no mesmo head canônico final.**

## What Happened

M005 fechou a convergência estrutural que M004 ainda deixava em aberto.

S01 primeiro tirou o controle plane de migrations de dentro do runtime da aplicação. `alembic history`, `heads`, `upgrade head` e `current` passaram a depender apenas de configuração de banco, com helpers de migration sob posse do próprio grafo e imports históricos protegidos contra side effects de `app.config.settings`, WuzAPI e Firebase.

Com o grafo operável, S02 publicou a fronteira histórica de Firebase de forma honesta. `user_sync_log` virou `firebase_sync_history` explícito e append-only; `audit_logs.firebase_uid` deixou de ser contrato vivo e ficou só como resíduo histórico/read-only; superfícies canônicas de users/admin/physicians e caches de sessão pararam de republicar `firebase_uid` como identidade operacional.

S03 então fechou o head canônico. O schema vivo de `users` foi republicado sob armazenamento neutro/canônico, `audit_logs` ficou alinhado ao contrato enum-backed final, e `firebase_sync_history` permaneceu apenas como histórico explícito. O ponto importante aqui não foi só “limpar” colunas: foi provar em Postgres real que `base -> head` e `m005_s02_t01_publish_firebase_history_boundary -> head` chegam ao mesmo fingerprint estrutural honesto.

S04 fechou o risco operacional restante. Em vez de parar na prova de schema, a slice montou um runner serial que prepara os histories `fresh` e `existing`, reaplica os packs críticos herdados de M004 no mesmo `TEST_DATABASE_URL`, sobe um uvicorn real nesse head consolidado e valida readiness, config pública e fluxo vivo de sessão (`login -> verify-session -> /users/me -> logout`).

Resultado do milestone: o controle plane Alembic, o schema final e o runtime montado contam a mesma história. O que sobrou de Firebase não é mais pivô funcional do sistema; é histórico explícito ou compatibilidade residual já empurrada para a próxima frente.

## Cross-Slice Verification

### Success criteria

1. **Alembic operável sem segredos de runtime fora do banco — met.**  
   Evidence: S01 passou `tests/migrations/test_alembic_operability.py` e os comandos scrubbed `history`, `heads`, `upgrade head` e `current` com apenas `DATABASE_URL`. A slice também registrou `alembic heads` em head único e `upgrade head && current` chegando ao mesmo head sem WuzAPI/Firebase env.

2. **Banco novo sobe de `base -> head` e termina compatível com o runtime canônico pós-M004, sem `firebase_uid`/sync Firebase como contrato vivo — met.**  
   Evidence: S02 publicou `firebase_sync_history` e removeu `firebase_uid` das superfícies canônicas; S03 provou em `tests/migrations/test_canonical_schema_head_convergence.py` que o caminho limpo converge para `m005_s03_t02_align_audit_history_head` com `users` canônico, `audit_logs.event_type` enum-backed e `firebase_sync_history` apenas histórico.

3. **Banco existente converge ao mesmo head e o que sobra de Firebase fica explicitamente histórico/arquival — met.**  
   Evidence: S02 passou `tests/migrations/test_firebase_historical_boundary.py`, cobrindo preservação/rename do histórico em banco existente; S03 provou que `m005_s02_t01_publish_firebase_history_boundary -> head` converge ao mesmo fingerprint estrutural do caminho limpo, sem reviver `firebase_uid` ou sync tables como contrato live.

4. **Revisions merge/no-op/one-way remanescentes ficam honestas e replayáveis — met.**  
   Evidence: S01 manteve a política de não reescrever o passado por estética, mas corrigiu exatamente as revisions que bloqueavam traversal: helpers históricos migraram para imports próprios de migration, backfills acoplados ao runtime passaram a importar serviços só quando existe trabalho pendente, e a clean replay path tolera objetos legados ausentes quando eles não pertencem ao caminho canônico. O resultado observável foi `history`, `heads`, `upgrade head` e `current` verdes em ambiente scrubbed.

5. **O backend sobe no head consolidado e os checks críticos herdados de M004 continuam verdes — met.**  
   Evidence: S04 passou o pack `tests/migrations/test_canonical_schema_head_convergence.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py`, depois executou `run-final-schema-proof.sh --fresh` e `--existing` com `status=passed` e `phase=live_auth_probe`, além da prova montada em `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py` sobre um uvicorn real no head final.

### Definition of done

- **Todas as slices S01–S04 concluídas:** confirmado pelo roadmap já marcado como `[x]` no contexto carregado.
- **Todas as slice summaries existem:** confirmado no filesystem por `find .gsd/milestones/M005/slices -maxdepth 2 -type f -name 'S*-SUMMARY.md'`, com `S01-SUMMARY.md`, `S02-SUMMARY.md`, `S03-SUMMARY.md` e `S04-SUMMARY.md` presentes.
- **Integração entre slices funciona de forma coerente:** confirmado pelo reaproveitamento explícito das superfícies entre slices: o harness de S01 alimenta a prova de convergência de S03; o head canônico de S03 é o alvo único do runner final de S04; e S04 reutiliza o mounted-proof publicado em M004/S06 em vez de abrir um segundo caminho de runtime.
- **Requirement/status closeout supported by proof:** R051 foi validado por S03; R053 foi validado por S04; `.gsd/REQUIREMENTS.md` já reflete esses status com as provas corretas.

**Unmet criteria:** none.

## Requirement Changes

- `R051`: active → validated — S01 tornou o controle plane Alembic operável só com config de banco, S02 publicou a fronteira histórica explícita, e S03 provou em Postgres real a convergência estrutural do head canônico para bancos `fresh` e `existing`.
- `R053`: active → validated — M004/S06 já tinha prova montada do runtime sem Firebase, e S04 fechou a lacuna restante com replay integrado `fresh`/`existing` no schema final mais backend real no mesmo head.

## Forward Intelligence

### What the next milestone should know
- O regression gate mais confiável deixado por M005 é `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh|--existing`. Se esse runner ficar verde, migrations, schema e backend montado continuam contando a mesma história.
- Para qualquer prova de runtime adjacente a migration, o schema compartilhado precisa continuar vindo de `alembic upgrade head` quando `TEST_DATABASE_URL` estiver definido. Voltar para `Base.metadata.create_all()` reabre drift e falsos negativos.
- O head canônico atual é `m005_s03_t02_align_audit_history_head`. M006 deve tratar qualquer remoção restante como purga de compatibilidade/resíduo, não como reabertura de convergência estrutural.

### What's fragile
- `TEST_DATABASE_URL` compartilhado — execuções paralelas contra o mesmo Postgres ainda podem resetar `public` por baixo de outra suite e fabricar falhas falsas.
- Porta `8000` no mounted proof — o runner final depende de conseguir subir um uvicorn real ali; outro processo ocupando a porta derruba a prova montada, não o schema.
- Espelhos de compatibilidade ainda vivos em `users` — o armazenamento canônico já é a fonte de verdade, mas M006 ainda precisa provar quais mirrors podem sair sem quebrar leitores remanescentes.

### Authoritative diagnostics
- `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/status.json` — melhor fonte única para fase, status final e ponteiros de log do runner integrado.
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — melhor sinal para drift estrutural entre caminho limpo e caminho existente.
- `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py` e `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/mounted-backend/backend.log` — melhores sinais para regressão de backend real no head final.

### What assumptions changed
- “Convergência de schema por si só fecha a frente” — não fechava; ainda faltava provar backend real no head convergido, o que só S04 cobriu.
- “Bastava deixar revisions antigas quietas” — não bastava; algumas precisavam de guards/import seams honestos para que o grafo fosse realmente replayável sem runtime secrets.

## Files Created/Modified

- `backend-hormonia/app/db/base.py` — moveu `Base` para um módulo settings-free usado pelo controle plane Alembic.
- `backend-hormonia/app/db/migrations.py` — centralizou bootstrap/DB URL helpers com falhas nomeadas para migration replay.
- `backend-hormonia/alembic/env.py` — passou a carregar migrations sem depender do runtime da app.
- `backend-hormonia/alembic/versions/m005_s02_t01_publish_firebase_history_boundary.py` — publicou `firebase_sync_history` como fronteira histórica explícita.
- `backend-hormonia/alembic/versions/m005_s03_t01_republish_users_canonical_contract.py` — republicou o contrato vivo de `users` sob colunas canônicas neutras.
- `backend-hormonia/alembic/versions/m005_s03_t02_align_audit_history_head.py` — alinhou o head final de auditoria/histórico ao schema canônico.
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — prova autoritativa do controle plane Alembic sem segredos da app.
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` — prova autoritativa da fronteira live-vs-histórico do legado Firebase.
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — prova autoritativa de convergência estrutural entre banco novo e existente.
- `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` — runner serial final para `fresh`/`existing` + replay pytest + backend montado.
- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — ganhou o modo backend-only reutilizado por S04.
- `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py` — prova viva de readiness/config/login no backend real sobre o head final.
- `.gsd/milestones/M005/M005-SUMMARY.md` — closeout consolidado do milestone.
- `.gsd/PROJECT.md` — estado atual do projeto ajustado para M005 concluído e M006 como foco ativo.
- `.gsd/STATE.md` — estado rápido avançado para M006.
- `.gsd/REQUIREMENTS.md` — requirement notes alinhadas ao closeout consolidado de M005.
