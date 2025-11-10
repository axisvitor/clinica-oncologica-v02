# Performance Guide

> Gerado em 09/11/2025 20:08 Hora oficial do Brasil

## Top 15 – Tabelas por tamanho total
| Tabela | Tamanho Tabela | Tamanho Índices | Total |
|--------|-----------------|-----------------|-------|
| public.messages | 32.0 KB | 288.0 KB | 320.0 KB |
| public.patients | 48.0 KB | 240.0 KB | 288.0 KB |
| public.error_logs | 48.0 KB | 208.0 KB | 256.0 KB |
| public.flow_template_versions | 176.0 KB | 80.0 KB | 256.0 KB |
| public.audit_logs | 64.0 KB | 144.0 KB | 208.0 KB |
| public.quiz_sessions | 16.0 KB | 176.0 KB | 192.0 KB |
| public.users | 16.0 KB | 144.0 KB | 160.0 KB |
| public.quiz_responses | 16.0 KB | 128.0 KB | 144.0 KB |
| public.security_audit_log | 8.0 KB | 112.0 KB | 120.0 KB |
| public.patient_flow_states | 16.0 KB | 88.0 KB | 104.0 KB |
| public.patient_onboarding_saga | 16.0 KB | 72.0 KB | 88.0 KB |
| public.quiz_templates | 32.0 KB | 48.0 KB | 80.0 KB |
| public.flow_kinds | 16.0 KB | 64.0 KB | 80.0 KB |
| public.webhook_events | 8.0 KB | 64.0 KB | 72.0 KB |
| public.admin_sessions | 8.0 KB | 64.0 KB | 72.0 KB |

## Índices potencialmente não utilizados
| Tabela | Índice | idx_scan | idx_tup_read | idx_tup_fetch |
|--------|--------|----------|--------------|---------------|
| public.admin_audit_log | admin_audit_log_pkey | 0 | 0 | 0 |
| public.admin_audit_log | idx_admin_audit_event_type | 0 | 0 | 0 |
| public.admin_audit_log | idx_admin_audit_ip | 0 | 0 | 0 |
| public.admin_audit_log | idx_admin_audit_resource | 0 | 0 | 0 |
| public.admin_audit_log | idx_admin_audit_severity | 0 | 0 | 0 |
| public.admin_audit_log | idx_admin_audit_timestamp | 0 | 0 | 0 |
| public.admin_audit_log | idx_admin_audit_user_id | 0 | 0 | 0 |
| public.admin_ip_blacklist | admin_ip_blacklist_ip_address_key | 0 | 0 | 0 |
| public.admin_ip_blacklist | admin_ip_blacklist_pkey | 0 | 0 | 0 |
| public.admin_ip_blacklist | idx_ip_blacklist_active | 0 | 0 | 0 |
| public.admin_ip_whitelist | admin_ip_whitelist_pkey | 0 | 0 | 0 |
| public.admin_ip_whitelist | idx_ip_whitelist_active | 0 | 0 | 0 |
| public.admin_ip_whitelist | idx_ip_whitelist_range | 0 | 0 | 0 |
| public.admin_ip_whitelist | unique_ip_or_range | 0 | 0 | 0 |
| public.admin_permissions | admin_permissions_name_key | 0 | 0 | 0 |
| public.admin_permissions | admin_permissions_pkey | 0 | 0 | 0 |
| public.admin_permissions | idx_admin_permissions_category | 0 | 0 | 0 |
| public.admin_role_permissions | admin_role_permissions_pkey | 0 | 0 | 0 |
| public.admin_role_permissions | idx_admin_role_permissions_role | 0 | 0 | 0 |
| public.admin_roles | admin_roles_name_key | 0 | 0 | 0 |
| public.admin_roles | admin_roles_pkey | 0 | 0 | 0 |
| public.admin_security_events | admin_security_events_pkey | 0 | 0 | 0 |
| public.admin_security_events | idx_security_events_ip | 0 | 0 | 0 |
| public.admin_security_events | idx_security_events_resolved | 0 | 0 | 0 |
| public.admin_security_events | idx_security_events_severity | 0 | 0 | 0 |
| public.admin_security_events | idx_security_events_timestamp | 0 | 0 | 0 |
| public.admin_security_events | idx_security_events_user_id | 0 | 0 | 0 |
| public.admin_sessions | admin_sessions_pkey | 0 | 0 | 0 |
| public.admin_sessions | admin_sessions_refresh_token_key | 0 | 0 | 0 |
| public.admin_sessions | admin_sessions_session_token_key | 0 | 0 | 0 |
| public.admin_sessions | idx_admin_sessions_active | 0 | 0 | 0 |
| public.admin_sessions | idx_admin_sessions_expires | 0 | 0 | 0 |
| public.admin_sessions | idx_admin_sessions_ip | 0 | 0 | 0 |
| public.admin_sessions | idx_admin_sessions_token | 0 | 0 | 0 |
| public.admin_sessions | idx_admin_sessions_user_id | 0 | 0 | 0 |
| public.admin_user_permissions | admin_user_permissions_pkey | 0 | 0 | 0 |
| public.admin_user_permissions | idx_admin_user_permissions_user | 0 | 0 | 0 |
| public.admin_users | admin_users_email_key | 0 | 0 | 0 |
| public.admin_users | admin_users_pkey | 0 | 0 | 0 |
| public.admin_users | idx_admin_users_active | 0 | 0 | 0 |
| public.admin_users | idx_admin_users_email | 0 | 0 | 0 |
| public.admin_users | idx_admin_users_last_login | 0 | 0 | 0 |
| public.admin_users | idx_admin_users_locked | 0 | 0 | 0 |
| public.admin_users | idx_admin_users_role | 0 | 0 | 0 |
| public.alerts | alerts_pkey | 0 | 0 | 0 |
| public.alerts | idx_alerts_acknowledged | 0 | 0 | 0 |
| public.alerts | idx_alerts_patient_id | 0 | 0 | 0 |
| public.alerts | idx_alerts_severity | 0 | 0 | 0 |
| public.alerts | idx_alerts_type | 0 | 0 | 0 |
| public.appointments | appointments_pkey | 0 | 0 | 0 |
