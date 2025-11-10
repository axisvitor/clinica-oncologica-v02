# Data Flow Guide

> Gerado em 09/11/2025 20:08 Hora oficial do Brasil

## Relacionamentos (FKs)

### public.admin_audit_log
- public.admin_audit_log.admin_user_id → public.admin_users.id
- public.admin_audit_log.session_id → public.admin_sessions.id

### public.admin_ip_blacklist
- public.admin_ip_blacklist.blocked_by → public.admin_users.id

### public.admin_ip_whitelist
- public.admin_ip_whitelist.added_by → public.admin_users.id

### public.admin_role_permissions
- public.admin_role_permissions.role_id → public.admin_roles.id
- public.admin_role_permissions.permission_id → public.admin_permissions.id

### public.admin_security_events
- public.admin_security_events.admin_user_id → public.admin_users.id
- public.admin_security_events.session_id → public.admin_sessions.id

### public.admin_sessions
- public.admin_sessions.admin_user_id → public.admin_users.id

### public.admin_user_permissions
- public.admin_user_permissions.admin_user_id → public.admin_users.id
- public.admin_user_permissions.permission_id → public.admin_permissions.id
- public.admin_user_permissions.granted_by → public.admin_users.id

### public.admin_users
- public.admin_users.created_by → public.admin_users.id
- public.admin_users.updated_by → public.admin_users.id

### public.alerts
- public.alerts.acknowledged_by → public.users.id
- public.alerts.patient_id → public.patients.id

### public.appointments
- public.appointments.doctor_id → public.users.id
- public.appointments.patient_id → public.patients.id

### public.audit_logs
- public.audit_logs.user_id → public.users.id

### public.contacts
- public.contacts.related_user_id → public.users.id
- public.contacts.related_patient_id → public.patients.id

### public.flow_analytics
- public.flow_analytics.flow_template_version_id → public.flow_template_versions.id
- public.flow_analytics.patient_id → public.patients.id

### public.flow_messages
- public.flow_messages.flow_template_version_id → public.flow_template_versions.id

### public.flow_states
- public.flow_states.patient_id → public.patients.id

### public.flow_template_shares
- public.flow_template_shares.flow_template_version_id → public.flow_template_versions.id
- public.flow_template_shares.shared_by → public.users.id
- public.flow_template_shares.shared_with → public.users.id

### public.flow_template_stats
- public.flow_template_stats.flow_template_version_id → public.flow_template_versions.id

### public.flow_template_versions
- public.flow_template_versions.flow_kind_id → public.flow_kinds.id
- public.flow_template_versions.created_by → public.users.id

### public.medical_reports
- public.medical_reports.generated_by → public.users.id
- public.medical_reports.patient_id → public.patients.id

### public.message_status_events
- public.message_status_events.message_id → public.messages.id

### public.messages
- public.messages.patient_id → public.patients.id

### public.patient_flow_states
- public.patient_flow_states.flow_template_version_id → public.flow_template_versions.id
- public.patient_flow_states.patient_id → public.patients.id

### public.patient_onboarding_saga
- public.patient_onboarding_saga.patient_id → public.patients.id
- public.patient_onboarding_saga.doctor_id → public.users.id

### public.patients
- public.patients.doctor_id → public.users.id

### public.quiz_responses
- public.quiz_responses.quiz_template_id → public.quiz_templates.id
- public.quiz_responses.quiz_session_id → public.quiz_sessions.id
- public.quiz_responses.patient_id → public.patients.id

### public.quiz_sessions
- public.quiz_sessions.quiz_template_id → public.quiz_templates.id
- public.quiz_sessions.patient_id → public.patients.id

### public.quiz_sessions_v2
- public.quiz_sessions_v2.template_version_id → public.quiz_template_versions_v2.id
- public.quiz_sessions_v2.patient_id → public.patients.id

### public.quiz_template_versions_v2
- public.quiz_template_versions_v2.template_id → public.quiz_templates.id
- public.quiz_template_versions_v2.created_by → public.users.id

### public.security_audit_log
- public.security_audit_log.patient_id → public.patients.id

### public.user_profiles
- public.user_profiles.user_id → public.users.id

### public.user_sync_log
- public.user_sync_log.supabase_user_id → public.users.id

### public.whatsapp_delivery_failures
- public.whatsapp_delivery_failures.reviewed_by → public.users.id
- public.whatsapp_delivery_failures.original_message_id → public.messages.id
- public.whatsapp_delivery_failures.patient_id → public.patients.id
