# M004: Convergência Canônica de Runtime

**Vision:** Primeiro passo da lapidação final da base: convergir o runtime oficial para um único caminho canônico sem Firebase, remover compatibilidades ainda vivas de auth/sessão e provar o stack montado funcionando nesse novo estado.

## Success Criteria

- O stack local autentica a equipe, restaura sessão e carrega `/dashboard`, `/admin` e `/whatsapp` sem depender de Firebase ou de superfícies legadas no caminho oficial.
- `firebase_uid`, `/session/*`, `X-Session-ID` e fallbacks legados em escopo deixam de ser parte viva do runtime oficial ou passam a ser rejeitados/tombstonados explicitamente.
- O frontend oficial para de depender funcionalmente de semântica/comentários de Firebase para auth/sessão.
- O milestone fecha com prova montada de runtime sem Firebase, não só com grep, diff e testes unitários.

## Key Risks / Unknowns

- Pode haver consumidores esquecidos de `/session/*`, `X-Session-ID` ou `Authorization: Bearer <session_id>` em superfícies ainda tratadas como oficiais.
- `firebase_uid` ainda vaza por cache, auditoria, tipos e payloads; remover dependência funcional sem deixar drift exige cuidado.
- O frontend oficial ainda carrega narrativa operacional de Firebase em partes de auth/admin e pode mascarar dependência real.
- Cortar o legado cedo demais sem guardrails pode quebrar loops críticos já estabilizados em M001–M003.

## Proof Strategy

- Consumidores esquecidos de runtime legado → retire in S01 by proving um mapa executável de resíduos vivos do runtime oficial e guardrails contra reintrodução.
- Dependência funcional de `firebase_uid` / caminhos duplos no backend → retire in S02 by proving login, verify-session, restore e logout no contrato canônico de sessão/`user_id`.
- Dependência funcional de Firebase no frontend oficial → retire in S03 by proving `/login`, `/dashboard` e `/admin` sobre o contrato session-first canônico.
- Superfícies legadas ainda oficialmente aceitas → retire in S04 by proving que o app oficial continua verde depois de aposentar, tombstonar ou rejeitar os contratos velhos em escopo.
- Resíduo funcional adjacente ainda tratando Firebase como vivo → retire in S05 by proving cache, auditoria, tipos/docs operacionais e módulos adjacentes alinhados ao runtime sem Firebase.
- Regressão do sistema montado → retire in S06 by proving o stack local completo verde sem Firebase nas superfícies críticas.

## Verification Classes

- Contract verification: suites focadas pytest/vitest, guardrails/grep verifiers, testes de rejeição/ausência para superfícies legadas e checagens de artefatos.
- Integration verification: stack local backend + frontend, probes diretos de auth/sessão e smoke browser para rotas críticas.
- Operational verification: backend/frontend sobem com envs de Firebase Auth em branco e permanecem saudáveis no contrato oficial.
- UAT / human verification: none.

## Milestone Definition of Done

This milestone is complete only when all are true:

- Todas as slices S01–S06 foram concluídas com seus verificadores verdes.
- O runtime oficial de auth/sessão e o frontend oficial estão de fato ligados ao caminho canônico sem Firebase.
- O entrypoint real existe e foi exercitado no stack local montado sem Firebase Auth.
- Os critérios de sucesso foram rechecados contra comportamento vivo, não apenas contra diffs estruturais.
- Os cenários finais de aceitação integrada passam e deixam claro o que ficou para M005 como dívida exclusivamente de schema/migração.

## Requirement Coverage

- Covers: R047, R048, R049, R050
- Partially covers: none
- Leaves for later: R051, R052, R053
- Orphan risks: none

## Slices

- [ ] **S01: Guardrails do corte canônico de runtime** `risk:high` `depends:[]`
  > After this: existe um verificador executável que mostra exatamente onde Firebase, `firebase_uid`, `/session/*`, `X-Session-ID` e bearer fallback ainda estão vivos no runtime oficial, e a suíte falha se novos resíduos reaparecem.

- [ ] **S02: Backend auth/sessão convergido para identidade canônica** `risk:high` `depends:[S01]`
  > After this: login, verify-session, restore e logout funcionam no backend pelo contrato canônico de sessão/`user_id`, com `firebase_uid` fora do happy path oficial.

- [ ] **S03: Frontend oficial convergido para contrato session-first canônico** `risk:medium` `depends:[S01,S02]`
  > After this: `/login`, `/dashboard` e `/admin` usam apenas o contrato oficial de auth/sessão, sem semântica funcional de Firebase no caminho feliz.

- [ ] **S04: Superfícies legadas de auth/sessão aposentadas** `risk:high` `depends:[S02,S03]`
  > After this: o app oficial deixa de precisar de `/session/*`, `X-Session-ID` e fallbacks legados em escopo; o que sobrar fica rejeitado ou tombstonado explicitamente.

- [ ] **S05: Resíduo funcional de Firebase removido do runtime adjacente** `risk:medium` `depends:[S02,S03]`
  > After this: cache, auditoria, tipos/docs operacionais e módulos adjacentes em escopo param de tratar Firebase como parte viva do sistema.

- [ ] **S06: Prova integrada de runtime sem Firebase** `risk:medium` `depends:[S04,S05]`
  > After this: o stack local sobe sem Firebase Auth e reprova login/restore/logout mais smoke de `/dashboard`, `/admin` e `/whatsapp` no estado montado.

## Boundary Map

### S01 → S02

Produces:
- Verificador executável do runtime oficial que mede referências vivas a `firebase_uid`, `/session/*`, `X-Session-ID`, bearer fallback e narrativa operacional de Firebase.
- Lista explícita de superfícies oficiais permitidas vs. superfícies legadas a aposentar em M004.

Consumes:
- nothing (first slice)

### S02 → S03

Produces:
- Contrato backend canônico de auth/sessão centrado em `user_id` para login, verify-session, restore e logout.
- Invariante de backend: o happy path oficial não depende de `firebase_uid` para resolver a identidade autenticada.

Consumes:
- Guardrails e mapa de resíduos produzidos em S01.

### S02 → S04

Produces:
- Lista concreta do que ainda sobra de `/session/*`, bearer fallback e `X-Session-ID` após a convergência do backend.
- Testes focados que distinguem caminho oficial de compatibilidade legada remanescente.

Consumes:
- Guardrails e limites de corte definidos em S01.

### S03 → S04

Produces:
- Frontend oficial (`/login`, `/dashboard`, `/admin`) consumindo apenas o contrato canônico de sessão.
- Inventário explícito dos últimos pontos do app oficial que ainda tocam superfícies legadas de auth/sessão.

Consumes:
- Contrato backend canônico produzido em S02.

### S04 → S05

Produces:
- Fronteira oficial de auth/sessão já estreitada: o que ficou legado está rejeitado ou tombstonado explicitamente.
- Ausência de dependência oficial em `/session/*`, `X-Session-ID` e fallback legado dentro do app oficial.

Consumes:
- Convergência backend/frontend produzida em S02 e S03.

### S04 → S06

Produces:
- Superfície oficial final de auth/sessão para ser exercitada no smoke de runtime montado.

Consumes:
- Guardrails de S01 e contrato canônico de S02/S03.

### S05 → S06

Produces:
- Cache, auditoria, tipos/docs operacionais e módulos adjacentes alinhados ao runtime sem Firebase.
- Lista explícita do que ficou para M005 como resíduo exclusivamente de schema/migração.

Consumes:
- Fronteira oficial estreitada em S04.
