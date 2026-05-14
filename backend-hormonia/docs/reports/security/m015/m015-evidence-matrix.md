# M015 Evidence Matrix

- Result: `passed`
- Generated at: `2026-05-14T18:19:07Z`
- Command: `./scripts/security/verify-m015-runtime-security.sh`
- Validator: `passed`

## Rows

| ID | Requirements | Status | Source seams | Evidence |
|---|---|---|---|---|
| db_tls_rls_runtime | R012, R014 | fresh_evidence | db | backend-hormonia/docs/reports/security/m015/db-seam-evidence.json |
| session_revocation_multi_process | R013, R014 | fresh_evidence | session | backend-hormonia/docs/reports/security/m015/session-seam-evidence.json |
| taskiq_worker_db_recheck | R013, R014 | fresh_evidence | session | backend-hormonia/docs/reports/security/m015/session-seam-evidence.json |
| provider_wuzapi_stub_boundary | R014, R015 | fresh_evidence | provider | backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json |
| provider_gemini_stub_boundary | R014, R015 | fresh_evidence | provider | backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json |
| private_upload_app_routes | R014, R017 | fresh_evidence | artifact | backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json |
| report_export_app_routes | R014, R017 | fresh_evidence | artifact | backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json |
| synthetic_only_no_live_providers | R015 | fresh_evidence | db, session, provider, artifact | backend-hormonia/docs/reports/security/m015/db-seam-evidence.json<br>backend-hormonia/docs/reports/security/m015/session-seam-evidence.json<br>backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json<br>backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json |
| redaction_safe_evidence | R017 | fresh_evidence | db, session, provider, artifact | backend-hormonia/docs/reports/security/m015/db-seam-evidence.json<br>backend-hormonia/docs/reports/security/m015/session-seam-evidence.json<br>backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json<br>backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json |
| strict_red_signal_closure | R018 | fixed_outcome | db, session, provider, artifact | backend-hormonia/docs/reports/security/m015/db-seam-evidence.json<br>backend-hormonia/docs/reports/security/m015/session-seam-evidence.json<br>backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json<br>backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json |

## Classified warnings

- `upload_quota_async_session_query_warning` — known_non_blocking_runtime_warning: Non-fatal runtime log warning from upload quota lookup; route catches it and S04 artifact proof passes. S05 keeps it classified so milestone validation can decide whether to remediate beyond security proof scope.

## Non-goals

- `no_live_provider_credentials`
- `no_production_systems_or_phi`
- `no_browser_frontend_flows`
- `no_cdn_object_storage_claim`
- `no_broad_dast_or_exploitation`
