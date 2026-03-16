# S03: Templates clínicos semeados

**Goal:** flow_kinds canônicos e templates com conteúdo clínico real existem no banco, carregáveis pelo EnhancedTemplateLoader.
**Demo:** `EnhancedTemplateLoader.get_message_for_day("onboarding", 3)` retorna o conteúdo clínico do dia 3 com send_mode e expects_response corretos. Mesmo para daily_follow_up dia 18.

## Must-Haves

- `flow_kinds` com kind_key `onboarding`, `daily_follow_up`, `quiz_mensal` existem no banco
- `flow_template_versions` com steps JSONB populado a partir dos snapshots markdown
- EnhancedTemplateLoader carrega e retorna conteúdo para todos os dias de onboarding (1-15) e daily follow-up (16-45)
- Cada step tem `send_mode` e `expects_response` corretos conforme snapshot

## Proof Level

- This slice proves: contract
- Real runtime required: yes (Postgres com dados)
- Human/UAT required: no

## Verification

- Query SQL: `SELECT kind_key FROM flow_kinds ORDER BY kind_key` retorna `daily_follow_up, onboarding, quiz_mensal`
- Query SQL: `SELECT template_name, jsonb_array_length(steps) FROM flow_template_versions WHERE is_active = true` mostra templates com steps
- Script Python: instancia EnhancedTemplateLoader e chama `get_message_for_day` para dias 1, 3, 7, 15 (onboarding) e 16, 18, 22 (daily follow-up) — todos retornam conteúdo

## Tasks

- [ ] **T01: Verificar e corrigir seeding de templates** `est:30m`
  - Why: a migration `9b4e2d1c7f66` deveria ter semeado templates dos snapshots markdown, mas precisa verificar se rodou corretamente e se os kind_keys são `onboarding`/`daily_follow_up` (não `initial_15_days`)
  - Files: `backend-hormonia/alembic/versions/9b4e2d1c7f66_sync_canonical_flow_templates_from_snapshots.py`, `backend-hormonia/app/templates/arquivo/db_snapshot/`
  - Do: verificar via SQL se flow_kinds e templates existem com conteúdo. Se a migration não rodou ou kind_keys estão errados, corrigir. Testar com EnhancedTemplateLoader que `get_message_for_day` retorna conteúdo para onboarding dias 1-15 e daily_follow_up dias 16-45.
  - Verify: queries SQL confirmam dados, script Python com template loader retorna conteúdo para todos os dias
  - Done when: template loader retorna conteúdo real para qualquer dia de onboarding ou daily follow-up

## Files Likely Touched

- `backend-hormonia/alembic/versions/` (se precisar de fix)
- `backend-hormonia/app/services/template_loader_pkg/loader.py` (verificação)
- `backend-hormonia/app/templates/arquivo/db_snapshot/` (leitura)
