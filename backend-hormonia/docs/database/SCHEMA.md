# Database Schema Documentation

## Tables Overview

| Table Name | Description |
| :--- | :--- |
| [ab_experiment_audit](tables/ab_experiment_audit.md) | |
| [ab_experiment_metrics](tables/ab_experiment_metrics.md) | |
| [ab_experiment_monitoring](tables/ab_experiment_monitoring.md) | |
| [ab_experiments](tables/ab_experiments.md) | |
| [ab_experiment_results](tables/ab_experiment_results.md) | |
| [ab_variant_assignments](tables/ab_variant_assignments.md) | |
| [admin_audit_log](tables/admin_audit_log.md) | |
| [admin_ip_blacklist](tables/admin_ip_blacklist.md) | |
| [admin_ip_whitelist](tables/admin_ip_whitelist.md) | |
| [admin_permissions](tables/admin_permissions.md) | |
| [admin_role_permissions](tables/admin_role_permissions.md) | |
| [admin_roles](tables/admin_roles.md) | |
| [admin_security_events](tables/admin_security_events.md) | |
| [admin_sessions](tables/admin_sessions.md) | |
| [admin_user_permissions](tables/admin_user_permissions.md) | |
| [admin_users](tables/admin_users.md) | |
| [alembic_version](tables/alembic_version.md) | |
| [alerts](tables/alerts.md) | |
| [appointments](tables/appointments.md) | |
| [audit_log_entries](tables/audit_log_entries.md) | |
| [audit_logs](tables/audit_logs.md) | |
| [audit_logs_archive](tables/audit_logs_archive.md) | |
| [audit_logs_archive_2025](tables/audit_logs_archive_2025.md) | |
| [audit_logs_archive_2026](tables/audit_logs_archive_2026.md) | |
| [audit_logs_archive_2027](tables/audit_logs_archive_2027.md) | |
| [audit_logs_archive_2028](tables/audit_logs_archive_2028.md) | |
| [audit_logs_archive_2029](tables/audit_logs_archive_2029.md) | |
| [audit_logs_archive_2030](tables/audit_logs_archive_2030.md) | |
| [audit_logs_archive_2031](tables/audit_logs_archive_2031.md) | |
| [audit_trail](tables/audit_trail.md) | |
| [consents](tables/consents.md) | |
| [contacts](tables/contacts.md) | |
| [error_logs](tables/error_logs.md) | |
| [flow_analytics](tables/flow_analytics.md) | |
| [flow_kinds](tables/flow_kinds.md) | |
| [flow_messages](tables/flow_messages.md) | |
| [flow_states](tables/flow_states.md) | |
| [flow_template_categories](tables/flow_template_categories.md) | |
| [flow_template_shares](tables/flow_template_shares.md) | |
| [flow_template_stats](tables/flow_template_stats.md) | |
| [flow_template_versions](tables/flow_template_versions.md) | |
| [lgpd_audit_logs](tables/lgpd_audit_logs.md) | LGPD compliance audit log for patient data access |
| [lgpd_data_access_requests](tables/lgpd_data_access_requests.md) | LGPD data subject access requests (DSAR) |
| [medical_reports](tables/medical_reports.md) | |
| [medications](tables/medications.md) | |
| [message_status_events](tables/message_status_events.md) | |
| [message_templates](tables/message_templates.md) | |
| [messages](tables/messages.md) | |
| [notifications](tables/notifications.md) | |
| [patient_flow_states](tables/patient_flow_states.md) | |
| [patient_onboarding_saga](tables/patient_onboarding_saga.md) | |
| [patient_summaries](tables/patient_summaries.md) | |
| [patients](tables/patients.md) | |
| [quiz_responses](tables/quiz_responses.md) | |
| [quiz_sessions](tables/quiz_sessions.md) | |
| [quiz_templates](tables/quiz_templates.md) | |
| [reports](tables/reports.md) | |
| [security_audit_log](tables/security_audit_log.md) | |
| [sessions](tables/sessions.md) | |
| [system_health_snapshots](tables/system_health_snapshots.md) | |
| [system_incidents](tables/system_incidents.md) | |
| [treatments](tables/treatments.md) | |
| [uploads](tables/uploads.md) | |
| [user_profiles](tables/user_profiles.md) | |
| [user_sync_log](tables/user_sync_log.md) | |
| [users](tables/users.md) | |
| [webhook_deliveries](tables/webhook_deliveries.md) | UUID default: gen_random_uuid() |
| [webhook_endpoints](tables/webhook_endpoints.md) | UUID default: gen_random_uuid() |
| [webhook_events](tables/webhook_events.md) | |
| [webhook_idempotency](tables/webhook_idempotency.md) | |
| [webhook_logs](tables/webhook_logs.md) | UUID default: gen_random_uuid() |
| [whatsapp_contacts](tables/whatsapp_contacts.md) | |
| [whatsapp_delivery_failures](tables/whatsapp_delivery_failures.md) | |
| [whatsapp_instances](tables/whatsapp_instances.md) | |
| [whatsapp_messages](tables/whatsapp_messages.md) |
 |

## Entity Relationship Diagram

```mermaid
erDiagram
    appointments {
        uuid id PK
        uuid patient_id 
        uuid doctor_id 
        string appointment_type 
        string status 
        datetime scheduled_at 
        int duration_minutes 
        datetime completed_at 
        datetime cancelled_at 
        TEXT pre_appointment_notes 
        TEXT post_appointment_notes 
        JSONB appointment_metadata 
        datetime created_at 
        datetime updated_at 
    }
    appointments }o--|| users : "references"
    appointments }o--|| patients : "references"
    whatsapp_contacts {
        TEXT id PK
        TEXT instance_name 
        TEXT phone_number 
        TEXT formatted_number 
        TEXT name 
        TEXT profile_picture_url 
        boolean is_whatsapp_user 
        datetime last_seen 
        datetime created_at 
        datetime updated_at 
        JSON contact_data 
    }
    security_audit_log {
        uuid id PK
        string event_type 
        string phone_number 
        uuid patient_id 
        TEXT message_content 
        JSONB source_metadata 
        int risk_score 
        string ip_address 
        string user_agent 
        string session_id 
        datetime created_at 
        JSONB additional_data 
        boolean alert_sent 
    }
    security_audit_log }o--|| patients : "references"
    quiz_sessions {
        uuid id PK
        uuid patient_id 
        uuid quiz_template_id 
        string status 
        int current_question 
        int total_questions 
        int answered_questions 
        NUMERIC(5,_2) score 
        NUMERIC(5,_2) max_score 
        boolean passed 
        datetime started_at 
        datetime completed_at 
        int time_spent_seconds 
        JSONB session_metadata 
        datetime created_at 
        datetime updated_at 
        datetime expiration_date 
    }
    quiz_sessions }o--|| patients : "references"
    quiz_sessions }o--|| quiz_templates : "references"
    flow_kinds {
        uuid id PK
        string kind_key 
        string display_name 
        TEXT description 
        boolean is_active 
        datetime created_at 
        datetime updated_at 
    }
    flow_template_versions {
        uuid id PK
        uuid flow_kind_id 
        int version_number 
        string template_name 
        TEXT description 
        JSONB steps 
        JSONB metadata 
        boolean is_active 
        boolean is_draft 
        datetime published_at 
        datetime deprecated_at 
        uuid created_by 
        datetime created_at 
        datetime updated_at 
    }
    flow_template_versions }o--|| users : "references"
    flow_template_versions }o--|| flow_kinds : "references"
    flow_template_categories {
        uuid id PK
        string category_key 
        string display_name 
        TEXT description 
        string icon 
        int sort_order 
        boolean is_active 
        datetime created_at 
    }
    error_logs {
        uuid id PK
        string error_type 
        TEXT error_message 
        TEXT stack_trace 
        JSONB context 
        int count 
        datetime first_seen 
        datetime last_seen 
        boolean resolved 
        string severity 
        datetime created_at 
        datetime updated_at 
    }
    system_health_snapshots {
        string status 
        DOUBLE_PRECISION health_score 
        JSONB services_status 
        JSONB metrics 
        datetime created_at 
        uuid id PK
        datetime updated_at 
    }
    flow_analytics {
        uuid id PK
        uuid flow_template_version_id 
        uuid patient_id 
        int total_steps 
        int completed_steps 
        NUMERIC(5,_2) success_rate 
        int avg_response_time_seconds 
        JSONB step_analytics 
        JSONB interaction_patterns 
        datetime period_start 
        datetime period_end 
        datetime calculated_at 
    }
    flow_analytics }o--|| flow_template_versions : "references"
    flow_analytics }o--|| patients : "references"
    flow_template_stats {
        uuid id PK
        uuid flow_template_version_id 
        int total_uses 
        int active_instances 
        int completed_instances 
        NUMERIC(5,_2) avg_completion_rate 
        NUMERIC(10,_2) avg_duration_hours 
        NUMERIC(3,_2) avg_rating 
        int total_ratings 
        datetime last_calculated_at 
    }
    flow_template_stats }o--|| flow_template_versions : "references"
    flow_template_shares {
        uuid id PK
        uuid flow_template_version_id 
        uuid shared_by 
        uuid shared_with 
        boolean can_view 
        boolean can_edit 
        boolean can_reshare 
        TEXT share_notes 
        datetime shared_at 
        datetime expires_at 
    }
    flow_template_shares }o--|| flow_template_versions : "references"
    flow_template_shares }o--|| users : "references"
    flow_template_shares }o--|| users : "references"
    system_incidents {
        string title 
        TEXT description 
        string severity 
        string status 
        string service_name 
        datetime started_at 
        datetime resolved_at 
        JSONB meta_data 
        datetime created_at 
        datetime updated_at 
        uuid id PK
    }
    admin_users {
        uuid id PK
        string email 
        string password_hash 
        string first_name 
        string last_name 
        string role 
        string department 
        string phone_number 
        boolean is_active 
        boolean email_verified 
        boolean two_factor_enabled 
        string two_factor_secret 
        boolean must_change_password 
        int failed_login_attempts 
        datetime locked_until 
        datetime last_login_at 
        INET last_login_ip 
        datetime last_password_change 
        int max_concurrent_sessions 
        datetime created_at 
        datetime updated_at 
        uuid created_by 
        uuid updated_by 
        JSONB metadata 
    }
    admin_users }o--|| admin_users : "references"
    admin_users }o--|| admin_users : "references"
    patient_onboarding_saga {
        uuid id PK
        uuid patient_id 
        uuid doctor_id 
        string status 
        int current_step 
        int retry_count 
        int max_retries 
        JSONB patient_data 
        JSONB execution_log 
        TEXT error_message 
        string error_type 
        datetime next_retry_at 
        datetime started_at 
        datetime completed_at 
        datetime failed_at 
        datetime created_at 
        datetime updated_at 
        datetime last_retry_at 
        JSONB step_data 
    }
    patient_onboarding_saga }o--|| users : "references"
    patient_onboarding_saga }o--|| patients : "references"
    admin_user_permissions {
        uuid admin_user_id PK
        uuid permission_id PK
        datetime granted_at 
        uuid granted_by 
    }
    admin_user_permissions }o--|| admin_users : "references"
    admin_user_permissions }o--|| admin_users : "references"
    admin_user_permissions }o--|| admin_permissions : "references"
    admin_permissions {
        uuid id PK
        string name 
        TEXT description 
        string category 
        datetime created_at 
    }
    admin_roles {
        uuid id PK
        string name 
        TEXT description 
        boolean is_system_role 
        datetime created_at 
        datetime updated_at 
    }
    admin_role_permissions {
        uuid role_id PK
        uuid permission_id PK
        datetime created_at 
    }
    admin_role_permissions }o--|| admin_permissions : "references"
    admin_role_permissions }o--|| admin_roles : "references"
    flow_messages {
        uuid id PK
        uuid flow_template_version_id 
        int step_number 
        string message_key 
        TEXT message_text 
        string message_type 
        JSONB buttons 
        JSONB list_items 
        JSONB conditions 
        int delay_seconds 
        datetime created_at 
    }
    flow_messages }o--|| flow_template_versions : "references"
    admin_sessions {
        uuid id PK
        uuid admin_user_id 
        string session_token 
        string refresh_token 
        INET ip_address 
        TEXT user_agent 
        string device_fingerprint 
        datetime created_at 
        datetime last_activity 
        datetime expires_at 
        boolean is_active 
        string logout_reason 
        JSONB metadata 
    }
    admin_sessions }o--|| admin_users : "references"
    webhook_events {
        uuid id PK
        string event_type 
        string source 
        JSONB payload 
        boolean processed 
        datetime processed_at 
        int retry_count 
        int max_retries 
        datetime next_retry_at 
        TEXT error_message 
        TEXT error_stack_trace 
        uuid related_message_id 
        uuid related_patient_id 
        string event_hash 
        boolean is_duplicate 
        uuid original_event_id 
        datetime created_at 
    }
    webhook_events }o--|| messages : "references"
    webhook_events }o--|| patients : "references"
    admin_audit_log {
        uuid id PK
        uuid admin_user_id 
        uuid session_id 
        string event_type 
        string event_category 
        string action 
        string resource_type 
        string resource_id 
        INET ip_address 
        TEXT user_agent 
        string endpoint 
        string http_method 
        JSONB details 
        JSONB changes 
        boolean success 
        TEXT error_message 
        datetime timestamp 
        int duration_ms 
        string severity 
    }
    admin_audit_log }o--|| admin_users : "references"
    admin_audit_log }o--|| admin_sessions : "references"
    admin_security_events {
        uuid id PK
        string event_type 
        string severity 
        INET ip_address 
        TEXT user_agent 
        uuid admin_user_id 
        uuid session_id 
        TEXT description 
        JSONB details 
        string endpoint 
        datetime detected_at 
        datetime resolved_at 
        TEXT resolution_notes 
        boolean auto_resolved 
        int risk_score 
        string threat_level 
    }
    admin_security_events }o--|| admin_users : "references"
    admin_security_events }o--|| admin_sessions : "references"
    admin_ip_whitelist {
        uuid id PK
        INET ip_address 
        CIDR ip_range 
        TEXT description 
        uuid added_by 
        datetime added_at 
        boolean is_active 
        datetime expires_at 
        datetime last_used_at 
        int usage_count 
    }
    admin_ip_whitelist }o--|| admin_users : "references"
    admin_ip_blacklist {
        uuid id PK
        INET ip_address 
        string reason 
        datetime blocked_at 
        uuid blocked_by 
        datetime expires_at 
        boolean is_permanent 
        uuid incident_id 
        string threat_level 
        int block_count 
        JSONB details 
        TEXT notes 
    }
    admin_ip_blacklist }o--|| admin_users : "references"
    user_profiles {
        uuid id PK
        uuid user_id 
        TEXT bio 
        string avatar_url 
        string phone 
        string specialty 
        string license_number 
        int years_of_experience 
        JSONB preferences 
        JSONB notification_settings 
        datetime created_at 
        datetime updated_at 
    }
    user_profiles }o--|| users : "references"
    audit_trail {
        uuid id PK
        string table_name 
        uuid record_id 
        string operation 
        JSONB old_data 
        JSONB new_data 
        JSONB changes 
        uuid actor_id 
        string actor_type 
        string actor_subject 
        INET ip_address 
        TEXT user_agent 
        string endpoint 
        datetime created_at 
    }
    audit_log_entries {
        uuid id PK
        string event_type 
        string entity_type 
        uuid entity_id 
        uuid user_id 
        JSONB old_values 
        JSONB new_values 
        JSONB metadata 
        INET ip_address 
        TEXT user_agent 
        datetime timestamp 
    }
    alembic_version {
        string version_num PK
    }
    alerts {
        uuid id PK
        uuid patient_id 
        string type 
        string severity 
        TEXT message 
        JSONB data 
        boolean acknowledged 
        uuid acknowledged_by 
        datetime acknowledged_at 
        datetime created_at 
        datetime updated_at 
    }
    alerts }o--|| users : "references"
    alerts }o--|| patients : "references"
    webhook_idempotency {
        string event_id PK
        string provider 
        string event_type 
        datetime received_at 
        datetime processed_at 
        datetime expires_at 
        string status 
        int retry_count 
        JSONB payload 
        JSONB response_data 
    }
    ab_experiments {
        string name 
        TEXT description 
        string message_template 
        JSONB target_population 
        int duration_days 
        DOUBLE_PRECISION traffic_split 
        string primary_metric 
        JSONB secondary_metrics 
        string status 
        datetime start_date 
        datetime end_date 
        boolean safety_checks_enabled 
        boolean medical_keyword_check 
        boolean manual_review_required 
        boolean emergency_stop_enabled 
        JSONB statistical_config 
        TEXT encrypted_config 
        string created_by 
        string started_by 
        string terminated_by 
        TEXT termination_reason 
        datetime terminated_at 
        int total_participants 
        int control_participants 
        int treatment_participants 
        JSONB results 
        boolean is_statistically_significant 
        string winner 
        DOUBLE_PRECISION effect_size 
        DOUBLE_PRECISION p_value 
        JSONB confidence_interval 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    ab_experiment_audit {
        uuid experiment_id 
        string action 
        string actor 
        string actor_type 
        JSONB action_details 
        JSONB previous_state 
        JSONB new_state 
        string ip_address 
        TEXT user_agent 
        string session_id 
        boolean hipaa_logged 
        boolean gdpr_compliant 
        datetime timestamp 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    ab_experiment_audit }o--|| ab_experiments : "references"
    audit_logs_archive {
        uuid id PK
        string event_type 
        string event_status 
        uuid user_id 
        string user_email 
        string firebase_uid 
        INET ip_address 
        string user_agent 
        string resource 
        string action 
        JSONB event_metadata 
        string message 
        string error_details 
        datetime created_at PK
        datetime updated_at 
        string session_id 
        string session_token_hash 
        string device_fingerprint 
        JSONB geolocation 
        string user_role 
        string event_category 
        string resource_type 
        uuid resource_id 
        JSONB resource_identifiers 
        string operation 
        string http_method 
        string endpoint 
        JSONB changes_before 
        JSONB changes_after 
        ARRAY changed_fields 
        TEXT description 
        JSONB query_params 
        string request_body_hash 
        string status 
        int http_status_code 
        string error_code 
        TEXT error_stack_trace 
        int duration_ms 
        string checksum 
        string previous_checksum 
        boolean integrity_verified 
        boolean reviewed 
        datetime reviewed_at 
        uuid reviewed_by 
        TEXT review_notes 
        boolean is_anomalous 
        NUMERIC(5,_2) anomaly_score 
        ARRAY anomaly_reasons 
        boolean alert_generated 
        datetime alert_sent_at 
        ARRAY alert_recipients 
        int retention_period_years 
        datetime archive_eligible_at 
        boolean archived 
        datetime archived_at 
        string archive_location 
    }
    audit_logs_archive_2025 {
        uuid id PK
        string event_type 
        string event_status 
        uuid user_id 
        string user_email 
        string firebase_uid 
        INET ip_address 
        string user_agent 
        string resource 
        string action 
        JSONB event_metadata 
        string message 
        string error_details 
        datetime created_at PK
        datetime updated_at 
        string session_id 
        string session_token_hash 
        string device_fingerprint 
        JSONB geolocation 
        string user_role 
        string event_category 
        string resource_type 
        uuid resource_id 
        JSONB resource_identifiers 
        string operation 
        string http_method 
        string endpoint 
        JSONB changes_before 
        JSONB changes_after 
        ARRAY changed_fields 
        TEXT description 
        JSONB query_params 
        string request_body_hash 
        string status 
        int http_status_code 
        string error_code 
        TEXT error_stack_trace 
        int duration_ms 
        string checksum 
        string previous_checksum 
        boolean integrity_verified 
        boolean reviewed 
        datetime reviewed_at 
        uuid reviewed_by 
        TEXT review_notes 
        boolean is_anomalous 
        NUMERIC(5,_2) anomaly_score 
        ARRAY anomaly_reasons 
        boolean alert_generated 
        datetime alert_sent_at 
        ARRAY alert_recipients 
        int retention_period_years 
        datetime archive_eligible_at 
        boolean archived 
        datetime archived_at 
        string archive_location 
    }
    audit_logs_archive_2026 {
        uuid id PK
        string event_type 
        string event_status 
        uuid user_id 
        string user_email 
        string firebase_uid 
        INET ip_address 
        string user_agent 
        string resource 
        string action 
        JSONB event_metadata 
        string message 
        string error_details 
        datetime created_at PK
        datetime updated_at 
        string session_id 
        string session_token_hash 
        string device_fingerprint 
        JSONB geolocation 
        string user_role 
        string event_category 
        string resource_type 
        uuid resource_id 
        JSONB resource_identifiers 
        string operation 
        string http_method 
        string endpoint 
        JSONB changes_before 
        JSONB changes_after 
        ARRAY changed_fields 
        TEXT description 
        JSONB query_params 
        string request_body_hash 
        string status 
        int http_status_code 
        string error_code 
        TEXT error_stack_trace 
        int duration_ms 
        string checksum 
        string previous_checksum 
        boolean integrity_verified 
        boolean reviewed 
        datetime reviewed_at 
        uuid reviewed_by 
        TEXT review_notes 
        boolean is_anomalous 
        NUMERIC(5,_2) anomaly_score 
        ARRAY anomaly_reasons 
        boolean alert_generated 
        datetime alert_sent_at 
        ARRAY alert_recipients 
        int retention_period_years 
        datetime archive_eligible_at 
        boolean archived 
        datetime archived_at 
        string archive_location 
    }
    ab_experiment_metrics {
        uuid experiment_id 
        int message_id 
        string anonymous_patient_id 
        string variant 
        string event_type 
        DOUBLE_PRECISION response_time_seconds 
        DOUBLE_PRECISION engagement_score 
        TEXT error_details 
        JSONB event_data 
        datetime event_timestamp 
        boolean processed 
        boolean included_in_analysis 
        string exclusion_reason 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    ab_experiment_metrics }o--|| ab_experiments : "references"
    audit_logs {
        uuid id PK
        string event_type 
        string event_status 
        uuid user_id 
        string user_email 
        string firebase_uid 
        INET ip_address 
        string user_agent 
        string resource 
        string action 
        JSONB event_metadata 
        string message 
        string error_details 
        datetime created_at 
        datetime updated_at 
        string session_id 
        string session_token_hash 
        string device_fingerprint 
        JSONB geolocation 
        string user_role 
        string event_category 
        string resource_type 
        uuid resource_id 
        JSONB resource_identifiers 
        string operation 
        string http_method 
        string endpoint 
        JSONB changes_before 
        JSONB changes_after 
        ARRAY changed_fields 
        TEXT description 
        JSONB query_params 
        string request_body_hash 
        string status 
        int http_status_code 
        string error_code 
        TEXT error_stack_trace 
        int duration_ms 
        string checksum 
        string previous_checksum 
        boolean integrity_verified 
        boolean reviewed 
        datetime reviewed_at 
        uuid reviewed_by 
        TEXT review_notes 
        boolean is_anomalous 
        NUMERIC(5,_2) anomaly_score 
        ARRAY anomaly_reasons 
        boolean alert_generated 
        datetime alert_sent_at 
        ARRAY alert_recipients 
        int retention_period_years 
        datetime archive_eligible_at 
        boolean archived 
        datetime archived_at 
        string archive_location 
    }
    audit_logs }o--|| users : "references"
    users {
        uuid id PK
        string email 
        string hashed_password 
        string full_name 
        string role 
        boolean is_active 
        string firebase_uid 
        string auth_provider 
        datetime firebase_last_sign_in 
        datetime firebase_created_at 
        boolean firebase_email_verified 
        string firebase_display_name 
        string firebase_photo_url 
        JSONB firebase_custom_claims 
        datetime last_firebase_sync 
        datetime created_at 
        datetime updated_at 
        JSONB permissions 
        int failed_login_attempts 
        boolean is_locked 
        datetime locked_until 
        boolean force_change_password 
        datetime last_password_change 
    }
    audit_logs_archive_2027 {
        uuid id PK
        string event_type 
        string event_status 
        uuid user_id 
        string user_email 
        string firebase_uid 
        INET ip_address 
        string user_agent 
        string resource 
        string action 
        JSONB event_metadata 
        string message 
        string error_details 
        datetime created_at PK
        datetime updated_at 
        string session_id 
        string session_token_hash 
        string device_fingerprint 
        JSONB geolocation 
        string user_role 
        string event_category 
        string resource_type 
        uuid resource_id 
        JSONB resource_identifiers 
        string operation 
        string http_method 
        string endpoint 
        JSONB changes_before 
        JSONB changes_after 
        ARRAY changed_fields 
        TEXT description 
        JSONB query_params 
        string request_body_hash 
        string status 
        int http_status_code 
        string error_code 
        TEXT error_stack_trace 
        int duration_ms 
        string checksum 
        string previous_checksum 
        boolean integrity_verified 
        boolean reviewed 
        datetime reviewed_at 
        uuid reviewed_by 
        TEXT review_notes 
        boolean is_anomalous 
        NUMERIC(5,_2) anomaly_score 
        ARRAY anomaly_reasons 
        boolean alert_generated 
        datetime alert_sent_at 
        ARRAY alert_recipients 
        int retention_period_years 
        datetime archive_eligible_at 
        boolean archived 
        datetime archived_at 
        string archive_location 
    }
    audit_logs_archive_2028 {
        uuid id PK
        string event_type 
        string event_status 
        uuid user_id 
        string user_email 
        string firebase_uid 
        INET ip_address 
        string user_agent 
        string resource 
        string action 
        JSONB event_metadata 
        string message 
        string error_details 
        datetime created_at PK
        datetime updated_at 
        string session_id 
        string session_token_hash 
        string device_fingerprint 
        JSONB geolocation 
        string user_role 
        string event_category 
        string resource_type 
        uuid resource_id 
        JSONB resource_identifiers 
        string operation 
        string http_method 
        string endpoint 
        JSONB changes_before 
        JSONB changes_after 
        ARRAY changed_fields 
        TEXT description 
        JSONB query_params 
        string request_body_hash 
        string status 
        int http_status_code 
        string error_code 
        TEXT error_stack_trace 
        int duration_ms 
        string checksum 
        string previous_checksum 
        boolean integrity_verified 
        boolean reviewed 
        datetime reviewed_at 
        uuid reviewed_by 
        TEXT review_notes 
        boolean is_anomalous 
        NUMERIC(5,_2) anomaly_score 
        ARRAY anomaly_reasons 
        boolean alert_generated 
        datetime alert_sent_at 
        ARRAY alert_recipients 
        int retention_period_years 
        datetime archive_eligible_at 
        boolean archived 
        datetime archived_at 
        string archive_location 
    }
    audit_logs_archive_2029 {
        uuid id PK
        string event_type 
        string event_status 
        uuid user_id 
        string user_email 
        string firebase_uid 
        INET ip_address 
        string user_agent 
        string resource 
        string action 
        JSONB event_metadata 
        string message 
        string error_details 
        datetime created_at PK
        datetime updated_at 
        string session_id 
        string session_token_hash 
        string device_fingerprint 
        JSONB geolocation 
        string user_role 
        string event_category 
        string resource_type 
        uuid resource_id 
        JSONB resource_identifiers 
        string operation 
        string http_method 
        string endpoint 
        JSONB changes_before 
        JSONB changes_after 
        ARRAY changed_fields 
        TEXT description 
        JSONB query_params 
        string request_body_hash 
        string status 
        int http_status_code 
        string error_code 
        TEXT error_stack_trace 
        int duration_ms 
        string checksum 
        string previous_checksum 
        boolean integrity_verified 
        boolean reviewed 
        datetime reviewed_at 
        uuid reviewed_by 
        TEXT review_notes 
        boolean is_anomalous 
        NUMERIC(5,_2) anomaly_score 
        ARRAY anomaly_reasons 
        boolean alert_generated 
        datetime alert_sent_at 
        ARRAY alert_recipients 
        int retention_period_years 
        datetime archive_eligible_at 
        boolean archived 
        datetime archived_at 
        string archive_location 
    }
    audit_logs_archive_2030 {
        uuid id PK
        string event_type 
        string event_status 
        uuid user_id 
        string user_email 
        string firebase_uid 
        INET ip_address 
        string user_agent 
        string resource 
        string action 
        JSONB event_metadata 
        string message 
        string error_details 
        datetime created_at PK
        datetime updated_at 
        string session_id 
        string session_token_hash 
        string device_fingerprint 
        JSONB geolocation 
        string user_role 
        string event_category 
        string resource_type 
        uuid resource_id 
        JSONB resource_identifiers 
        string operation 
        string http_method 
        string endpoint 
        JSONB changes_before 
        JSONB changes_after 
        ARRAY changed_fields 
        TEXT description 
        JSONB query_params 
        string request_body_hash 
        string status 
        int http_status_code 
        string error_code 
        TEXT error_stack_trace 
        int duration_ms 
        string checksum 
        string previous_checksum 
        boolean integrity_verified 
        boolean reviewed 
        datetime reviewed_at 
        uuid reviewed_by 
        TEXT review_notes 
        boolean is_anomalous 
        NUMERIC(5,_2) anomaly_score 
        ARRAY anomaly_reasons 
        boolean alert_generated 
        datetime alert_sent_at 
        ARRAY alert_recipients 
        int retention_period_years 
        datetime archive_eligible_at 
        boolean archived 
        datetime archived_at 
        string archive_location 
    }
    ab_experiment_monitoring {
        uuid experiment_id 
        datetime monitoring_period_start 
        datetime monitoring_period_end 
        DOUBLE_PRECISION control_response_rate 
        DOUBLE_PRECISION treatment_response_rate 
        DOUBLE_PRECISION control_error_rate 
        DOUBLE_PRECISION treatment_error_rate 
        int safety_violations_count 
        int medical_content_alerts 
        int patient_complaints 
        boolean response_rate_threshold_breached 
        boolean error_rate_threshold_breached 
        boolean engagement_threshold_breached 
        JSONB alerts_sent 
        boolean emergency_stop_triggered 
        JSONB monitoring_data 
        datetime processed_at 
        datetime next_check_at 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    ab_experiment_monitoring }o--|| ab_experiments : "references"
    audit_logs_archive_2031 {
        uuid id PK
        string event_type 
        string event_status 
        uuid user_id 
        string user_email 
        string firebase_uid 
        INET ip_address 
        string user_agent 
        string resource 
        string action 
        JSONB event_metadata 
        string message 
        string error_details 
        datetime created_at PK
        datetime updated_at 
        string session_id 
        string session_token_hash 
        string device_fingerprint 
        JSONB geolocation 
        string user_role 
        string event_category 
        string resource_type 
        uuid resource_id 
        JSONB resource_identifiers 
        string operation 
        string http_method 
        string endpoint 
        JSONB changes_before 
        JSONB changes_after 
        ARRAY changed_fields 
        TEXT description 
        JSONB query_params 
        string request_body_hash 
        string status 
        int http_status_code 
        string error_code 
        TEXT error_stack_trace 
        int duration_ms 
        string checksum 
        string previous_checksum 
        boolean integrity_verified 
        boolean reviewed 
        datetime reviewed_at 
        uuid reviewed_by 
        TEXT review_notes 
        boolean is_anomalous 
        NUMERIC(5,_2) anomaly_score 
        ARRAY anomaly_reasons 
        boolean alert_generated 
        datetime alert_sent_at 
        ARRAY alert_recipients 
        int retention_period_years 
        datetime archive_eligible_at 
        boolean archived 
        datetime archived_at 
        string archive_location 
    }
    quiz_response_migration_log {
        uuid id PK
        uuid quiz_response_id 
        TEXT original_value 
        JSONB converted_value 
        TEXT conversion_status 
        TEXT error_message 
        datetime migrated_at 
    }
    flow_states {
        uuid id PK
        uuid patient_id 
        string flow_type 
        int current_step 
        datetime started_at 
        datetime completed_at 
        JSONB state_data 
        datetime created_at 
        datetime updated_at 
    }
    flow_states }o--|| patients : "references"
    ab_experiment_results {
        uuid experiment_id 
        datetime analysis_timestamp 
        string analysis_version 
        string analyst_id 
        int control_sample_size 
        int treatment_sample_size 
        int total_sample_size 
        string primary_metric_name 
        DOUBLE_PRECISION control_primary_value 
        DOUBLE_PRECISION treatment_primary_value 
        DOUBLE_PRECISION primary_metric_difference 
        DOUBLE_PRECISION primary_metric_relative_change 
        string statistical_test_type 
        DOUBLE_PRECISION p_value 
        DOUBLE_PRECISION alpha 
        boolean is_statistically_significant 
        DOUBLE_PRECISION cohens_d 
        string effect_size_magnitude 
        DOUBLE_PRECISION confidence_level 
        DOUBLE_PRECISION ci_lower_bound 
        DOUBLE_PRECISION ci_upper_bound 
        DOUBLE_PRECISION ci_margin_of_error 
        string winner 
        DOUBLE_PRECISION winner_confidence 
        TEXT recommendation 
        JSONB secondary_metrics_results 
        JSONB detailed_results 
        JSONB variant_performance 
        DOUBLE_PRECISION data_quality_score 
        JSONB anomalies_detected 
        JSONB quality_warnings 
        JSONB projected_impact 
        JSONB cost_benefit_analysis 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    ab_experiment_results }o--|| ab_experiments : "references"
    ab_variant_assignments {
        uuid experiment_id 
        string anonymous_patient_id 
        string variant 
        string safety_level 
        string assignment_hash 
        string assignment_reason 
        datetime assigned_at 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    ab_variant_assignments }o--|| ab_experiments : "references"
    uploads {
        uuid user_id 
        string file_name 
        int file_size 
        string file_type 
        string storage_path 
        string storage_provider 
        string content_hash 
        JSONB file_metadata 
        boolean is_public 
        boolean virus_scanned 
        boolean virus_clean 
        datetime deleted_at 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    uploads }o--|| users : "references"
    webhook_endpoints {
        uuid id PK
        string url 
        string description 
        string status 
        string secret 
        JSONB events 
        JSONB headers 
        int timeout 
        boolean retry_enabled 
        int max_retries 
        int success_count 
        int failure_count 
        datetime last_triggered_at 
        datetime created_at 
        datetime updated_at 
    }
    webhook_deliveries {
        uuid id PK
        uuid webhook_id 
        string event_type 
        JSONB payload 
        string status 
        int attempt 
        int status_code 
        DOUBLE_PRECISION response_time_ms 
        TEXT response_body 
        TEXT error 
        datetime created_at 
        datetime completed_at 
        datetime next_retry_at 
    }
    webhook_deliveries }o--|| webhook_endpoints : "references"
    messages {
        uuid id PK
        uuid patient_id 
        string direction 
        string type 
        TEXT content 
        JSONB message_metadata 
        string whatsapp_id 
        string status 
        datetime scheduled_for 
        datetime sent_at 
        datetime delivered_at 
        datetime read_at 
        datetime created_at 
        datetime updated_at 
        string delivery_status 
        int retry_count 
        datetime last_retry_at 
        TEXT failure_reason 
        datetime next_retry_at 
        string idempotency_key 
        string priority 
    }
    messages }o--|| patients : "references"
    webhook_logs {
        uuid id PK
        uuid webhook_id 
        string event_type 
        string action 
        JSONB details 
        datetime created_at 
    }
    webhook_logs }o--|| webhook_endpoints : "references"
    patients {
        uuid id PK
        uuid doctor_id 
        string name 
        DATE birth_date 
        string treatment_type 
        DATE treatment_start_date 
        string treatment_phase 
        TEXT diagnosis 
        string flow_state 
        int current_day 
        TEXT doctor_notes 
        datetime created_at 
        datetime updated_at 
        JSONB metadata 
        datetime deleted_at 
        TEXT cpf_encrypted 
        string cpf_hash 
        string idempotency_key 
        BYTEA email_encrypted 
        string email_hash 
        BYTEA phone_encrypted 
        string phone_hash 
    }
    patients }o--|| users : "references"
    message_templates {
        string name 
        TEXT content 
        JSONB variables 
        string message_type 
        string media_url 
        boolean is_active 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    patient_flow_states {
        uuid id PK
        uuid patient_id 
        uuid flow_template_version_id 
        int current_step 
        JSONB step_data 
        string status 
        datetime started_at 
        datetime last_interaction_at 
        datetime completed_at 
        datetime next_scheduled_at 
        JSONB flow_metadata 
        datetime created_at 
        datetime updated_at 
        int version 
    }
    patient_flow_states }o--|| flow_template_versions : "references"
    patient_flow_states }o--|| patients : "references"
    whatsapp_delivery_failures {
        uuid id PK
        uuid patient_id 
        string phone_number 
        string message_type 
        TEXT message_content 
        TEXT error_message 
        string error_code 
        int retry_count 
        int max_retries 
        datetime next_retry_at 
        datetime last_retry_at 
        string status 
        datetime resolved_at 
        JSONB dlq_metadata 
        uuid reviewed_by 
        uuid original_message_id 
        datetime created_at 
        datetime updated_at 
    }
    whatsapp_delivery_failures }o--|| messages : "references"
    whatsapp_delivery_failures }o--|| patients : "references"
    whatsapp_delivery_failures }o--|| users : "references"

    quiz_responses {
        uuid id PK
        uuid patient_id 
        uuid quiz_template_id 
        uuid quiz_session_id 
        string question_id 
        TEXT question_text 
        string response_type 
        TEXT response_value_text_backup 
        boolean is_correct 
        NUMERIC(5,_2) points_earned 
        JSONB response_metadata 
        datetime responded_at 
        int response_time_seconds 
        datetime created_at 
        datetime updated_at 
        TEXT other_text 
        JSONB response_value 
    }
    quiz_responses }o--|| patients : "references"
    quiz_responses }o--|| quiz_templates : "references"
    quiz_responses }o--|| quiz_sessions : "references"
    message_status_events {
        uuid id PK
        uuid message_id 
        string status 
        string previous_status 
        string whatsapp_id 
        datetime whatsapp_timestamp 
        string error_code 
        TEXT error_message 
        int retry_count 
        JSONB metadata 
        string evolution_event_type 
        JSONB evolution_payload 
        datetime created_at 
    }
    message_status_events }o--|| messages : "references"
    medical_reports {
        uuid id PK
        uuid patient_id 
        uuid generated_by 
        DATE period_start 
        DATE period_end 
        TEXT summary 
        JSONB insights 
        JSONB charts_data 
        JSONB alerts 
        string report_type 
        JSONB report_metadata 
        datetime created_at 
        datetime updated_at 
    }
    medical_reports }o--|| users : "references"
    medical_reports }o--|| patients : "references"
    contacts {
        uuid id PK
        string name 
        string email 
        string phone 
        string contact_type 
        uuid related_patient_id 
        uuid related_user_id 
        TEXT notes 
        ARRAY tags 
        JSONB contact_metadata 
        datetime created_at 
        datetime updated_at 
    }
    contacts }o--|| patients : "references"
    contacts }o--|| users : "references"
    notifications {
        uuid id PK
        uuid user_id 
        uuid related_patient_id 
        string notification_type 
        string priority 
        string title 
        TEXT message 
        string action_url 
        string action_label 
        JSONB notification_metadata 
        boolean is_read 
        datetime read_at 
        boolean is_archived 
        datetime archived_at 
        datetime expires_at 
        datetime created_at 
        datetime updated_at 
    }
    notifications }o--|| patients : "references"
    notifications }o--|| users : "references"
    patient_summaries {
        uuid id PK
        uuid patient_id 
        uuid generated_by 
        DATE start_date 
        DATE end_date 
        JSONB content 
        BYTEA pdf_data 
        int token_usage 
        string model_used 
        int generation_time_ms 
        datetime created_at 
        datetime updated_at 
    }
    patient_summaries }o--|| users : "references"
    patient_summaries }o--|| patients : "references"
    consents {
        uuid patient_id 
        uuid consented_by_id 
        string consent_type 
        string status 
        string title 
        TEXT description 
        TEXT legal_text 
        datetime granted_at 
        datetime revoked_at 
        datetime expires_at 
        string version 
        uuid previous_consent_id 
        JSONB signature_data 
        uuid witness_id 
        TEXT revocation_reason 
        boolean is_required 
        boolean is_active 
        JSONB consent_metadata 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    consents }o--|| users : "references"
    consents }o--|| patients : "references"
    consents }o--|| users : "references"
    reports {
        uuid patient_id 
        string type 
        string title 
        JSONB content 
        BYTEA pdf_data 
        string status 
        datetime generated_at 
        JSONB metadata 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    reports }o--|| patients : "references"
    treatments {
        uuid patient_id 
        uuid doctor_id 
        string treatment_type 
        string status 
        DATE start_date 
        DATE end_date 
        string planned_sessions 
        string completed_sessions 
        TEXT diagnosis 
        string protocol 
        TEXT notes 
        boolean is_active 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    treatments }o--|| users : "references"
    treatments }o--|| patients : "references"
    medications {
        uuid patient_id 
        uuid prescribed_by_id 
        uuid treatment_id 
        string name 
        string active_ingredient 
        string dosage 
        string frequency 
        string route 
        DATE prescription_date 
        DATE start_date 
        DATE end_date 
        NUMERIC(10,_2) quantity 
        int refills_allowed 
        int refills_remaining 
        TEXT instructions 
        TEXT warnings 
        TEXT side_effects 
        boolean is_active 
        DATE discontinued_date 
        TEXT discontinuation_reason 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    medications }o--|| patients : "references"
    medications }o--|| users : "references"
    medications }o--|| treatments : "references"
    quiz_templates {
        uuid id PK
        string name 
        string version 
        TEXT description 
        JSONB questions 
        boolean is_active 
        string category 
        ARRAY tags 
        int passing_score 
        int time_limit_minutes 
        boolean randomize_questions 
        datetime created_at 
        datetime updated_at 
    }

    sessions {
        uuid user_id 
        string session_token 
        string refresh_token 
        string device_id 
        string device_name 
        string device_type 
        string ip_address 
        TEXT user_agent 
        JSONB location 
        datetime last_activity 
        datetime expires_at 
        boolean is_active 
        datetime revoked_at 
        TEXT revocation_reason 
        boolean is_suspicious 
        string risk_score 
        JSONB session_metadata 
        uuid id PK
        datetime created_at 
        datetime updated_at 
    }
    sessions }o--|| users : "references"
    user_sync_log {
        uuid id PK
        string firebase_uid 
        uuid supabase_user_id 
        string sync_action 
        string sync_status 
        JSONB firebase_data 
        JSONB supabase_data 
        TEXT error_message 
        int retry_count 
        datetime synced_at 
        datetime created_at 
        datetime updated_at 
        uuid user_id 
        string operation 
        string sync_direction 
        JSONB changes 
        boolean success 
    }
    user_sync_log }o--|| users : "references"
    user_sync_log }o--|| users : "references"
    whatsapp_instances {
        TEXT id PK
        TEXT name 
        TEXT status 
        TEXT qr_code 
        TEXT webhook_url 
        TEXT phone_number 
        TEXT profile_name 
        TEXT profile_picture_url 
        boolean is_connected 
        datetime created_at 
        datetime updated_at 
        datetime last_activity 
        JSON settings 
    }
    whatsapp_messages {
        TEXT id PK
        TEXT instance_name 
        TEXT chat_id 
        TEXT sender_id 
        TEXT recipient_id 
        TEXT message_type 
        TEXT content 
        TEXT media_url 
        TEXT media_caption 
        TEXT status 
        TEXT external_id 
        datetime created_at 
        datetime updated_at 
        datetime sent_at 
        datetime delivered_at 
        datetime read_at 
        datetime failed_at 
        int retry_count 
        TEXT error_message 
        JSON message_data 
    }
```
