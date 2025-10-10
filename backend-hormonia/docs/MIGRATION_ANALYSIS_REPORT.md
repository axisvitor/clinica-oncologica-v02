
====================================================================================================
ALEMBIC MIGRATION ANALYSIS REPORT
====================================================================================================

SUMMARY
  Total migrations: 69
  Root migrations (no parent): 3
  Merge migrations: 2
  Orphaned migrations (not referenced): 5

NAMING PATTERNS
  Old numbered (001_, 002_, etc.): 37
  Date-based (20251009_, etc.): 22
  Hash-based (3e0261295d8a_): 4
  Descriptive (add_performance_indexes, etc.): 6

ALL MIGRATIONS
File                                                                   | Revision                            | Down Revision(s)
------------------------------------------------------------------------------------------------------------------------------------------------------
001_add_whatsapp_tables.py                                             | 001_whatsapp                        | 001_initial
001_initial_migration.py                                               | 001_initial                         | None [ROOT]
002_add_duplicate_detection_rpcs.py                                    | 004_duplicate_detection             | 003_flow_templates
002_add_flow_templates.py                                              | 003_flow_templates                  | 002_quiz_metadata
002_add_quiz_sessions_table.py                                         | 005_quiz_sessions                   | 004_duplicate_detection
003_add_quiz_constraints.py                                            | 009_quiz_constraints_v2             | 008_quiz_constraints_v1
004_fix_user_role_enum.py                                              | 010_user_role_enum                  | 009_quiz_constraints_v2
005_add_other_text_to_quiz_responses.py                                | 011_other_text                      | 010_user_role_enum
006_add_ai_audit_logs_table.py                                         | 012_ai_audit_logs                   | 011_other_text
011_remove_nurse_role.py                                               | 011_remove_nurse_role               | 010_user_role_enum
013_fix_quiz_response_type_constraint.py                               | 013_fix_quiz_response_type_constraint | 012_ai_audit_logs
014_add_cpf_column_migrate_metadata.py                                 | 014_add_cpf_migrate_metadata        | 013_fix_quiz_response_type_constraint
015_add_template_versioning_tables.py                                  | 015_add_template_versioning_tables  | add_performance_indexes
016_backfill_template_versioning_data.py                               | 016_backfill_template_versioning_data | 015_add_template_versioning_tables
017_remove_legacy_templates.py                                         | 017_remove_legacy_templates         | 016_backfill_template_versioning_data
018_create_message_status_events.py                                    | 018_message_status_events           | 3e0261295d8a
019_create_webhook_events.py                                           | 019_webhook_events                  | 018_message_status_events
020_add_message_status_events_indexes.py                               | 020_message_status_indexes          | 019_webhook_events
021_add_webhook_events_indexes.py                                      | 021_webhook_events_indexes          | 020_message_status_indexes
022_create_ab_experiments.py                                           | 022_ab_experiments                  | 021_webhook_events_indexes
023_create_ab_variant_assignments.py                                   | 023_ab_variant_assignments          | 022_ab_experiments
024_create_ab_experiment_metrics.py                                    | 024_ab_experiment_metrics           | 023_ab_variant_assignments
025_create_ab_experiment_results.py                                    | 025_ab_experiment_results           | 024_ab_experiment_metrics
026_create_ab_experiment_audit.py                                      | 026_ab_experiment_audit             | 025_ab_experiment_results
027_create_ab_experiment_monitoring.py                                 | 027_ab_experiment_monitoring        | 026_ab_experiment_audit
028_add_ab_testing_indexes.py                                          | 028_ab_testing_indexes              | 027_ab_experiment_monitoring
029_create_quiz_questions.py                                           | 029_quiz_questions                  | 028_ab_testing_indexes
030_fix_audit_table_naming.py                                          | 030_fix_audit_naming                | 029_quiz_questions
031_add_users_email_active_index.py                                    | 031_users_email_active_idx          | 030_fix_audit_naming
032_add_messages_whatsapp_id_index.py                                  | 032_messages_whatsapp_idx           | 031_users_email_active_idx
033_add_audit_user_timestamp_index.py                                  | 033_audit_user_timestamp_idx        | 032_messages_whatsapp_idx
034_add_patient_flow_states_active_index.py                            | 034_flow_states_active_idx          | 033_audit_user_timestamp_idx
035_add_composite_performance_indexes.py                               | 035_composite_indexes               | 034_flow_states_active_idx
036_add_foreign_key_constraints.py                                     | 036_foreign_keys                    | 035_composite_indexes
037_add_automated_triggers.py                                          | 037_triggers                        | 036_foreign_keys
038_add_jsonb_gin_indexes.py                                           | 038_jsonb_indexes                   | 037_triggers
039_add_fulltext_search_indexes.py                                     | 039_fulltext_search                 | 038_jsonb_indexes
20240831_add_quiz_session_metadata.py                                  | 002_quiz_metadata                   | 001_whatsapp
20250929_200001_add_users_email_active_index.py                        | 20250929_200001                     | add_performance_indexes
20250929_200002_add_messages_whatsapp_id_index.py                      | 20250929_200002                     | 20250929_200001
20250929_200003_add_audit_logs_user_timestamp_index.py                 | 20250929_200003                     | 20250929_200002
20250929_200004_add_patient_flow_states_active_index.py                | 20250929_200004                     | 20250929_200003
20250929_200005_add_message_status_events_indexes.py                   | 20250929_200005                     | 20250929_200004
20250929_200006_add_webhook_events_indexes.py                          | 20250929_200006                     | 20250929_200005
20250929_200007_add_patients_doctor_id_index.py                        | 20250929_200007                     | 20250929_200006
20250929_200008_add_messages_patient_status_index.py                   | 20250929_200008                     | 20250929_200007
20250929_200009_add_flow_states_updated_index.py                       | 20250929_200009                     | 20250929_200008
20250929_200010_add_quiz_responses_patient_index.py                    | 20250929_200010                     | 20250929_200009
20250930_011500_add_critical_performance_indexes.py                    | 20250930_011500                     | 20250929_200010
20250930_add_firebase_fields.py                                        | add_firebase_fields                 | 20250930_011500
20251006_add_risk_assessment_indexes.py                                | 20251006_add_risk_assessment_indexes | 20251006_add_user_sync_log_updated_at
20251006_add_user_sync_log_updated_at.py                               | 20251006_add_user_sync_log_updated_at | add_firebase_fields
20251007_add_message_sending_status.py                                 | 20251007_add_sending_status         | 20251006_add_risk_assessment_indexes
20251009_210800_add_gin_indexes_for_search.py                          | 20251009_210800                     | add_performance_indexes
20251009_225600_add_quiz_session_to_alerts.py                          | 20251009_225600                     | 20251009_210800 [ORPHAN]
20251009_230000_add_whatsapp_delivery_failures.py                      | UNKNOWN                             | None [ROOT]
20251009_235500_add_webhook_idempotency.py                             | UNKNOWN                             | None [ROOT]
20251009_235900_add_delivery_status.py                                 | 20251009_235900                     | 20251009_235500
20251010_000000_add_unique_quiz_session_constraint.py                  | 20251010_000000                     | 20251009_235900 [ORPHAN]
3d3c49dd21c2_merge_multiple_heads.py                                   | 3d3c49dd21c2                        | 039_fulltext_search, 20251007_add_sending_status, create_audit_retention [MERGE]
3e0261295d8a_add_missing_user_roles.py                                 | 3e0261295d8a                        | 54ab19a5b23f
5479068ccdaa_rename_audit_log_metadata_to_event_.py                    | 5479068ccdaa                        | 3d3c49dd21c2 [ORPHAN]
54ab19a5b23f_merge_multiple_heads.py                                   | 54ab19a5b23f                        | 011_remove_nurse_role, 017_remove_legacy_templates, add_dedicated_patient_columns [MERGE]
add_audit_log_entries_table.py                                         | 006_audit_log                       | 005_quiz_sessions
add_dedicated_patient_columns.py                                       | add_dedicated_patient_columns       | 014_add_cpf_migrate_metadata
add_flow_analytics_tables.py                                           | 007_flow_analytics                  | 006_audit_log
add_performance_indexes.py                                             | add_performance_indexes             | 014_add_cpf_migrate_metadata
add_quiz_constraints.py                                                | 008_quiz_constraints_v1             | 007_flow_analytics
create_audit_retention_functions.py                                    | create_audit_retention              | add_performance_indexes

====================================================================================================
ROOT MIGRATIONS (Entry Points)
====================================================================================================
  001_initial_migration.py                                               -> 001_initial
  20251009_230000_add_whatsapp_delivery_failures.py                      -> UNKNOWN
  20251009_235500_add_webhook_idempotency.py                             -> UNKNOWN

====================================================================================================
MERGE MIGRATIONS
====================================================================================================
  3d3c49dd21c2_merge_multiple_heads.py                                   -> 3d3c49dd21c2
    Merges: 039_fulltext_search, 20251007_add_sending_status, create_audit_retention

  54ab19a5b23f_merge_multiple_heads.py                                   -> 54ab19a5b23f
    Merges: 011_remove_nurse_role, 017_remove_legacy_templates, add_dedicated_patient_columns


====================================================================================================
MIGRATION CHAINS
====================================================================================================

Chain starting from: 001_initial (001_initial_migration.py)
  -> 001_whatsapp: 001_add_whatsapp_tables.py
    -> 002_quiz_metadata: 20240831_add_quiz_session_metadata.py
      -> 003_flow_templates: 002_add_flow_templates.py
        -> 004_duplicate_detection: 002_add_duplicate_detection_rpcs.py
          -> 005_quiz_sessions: 002_add_quiz_sessions_table.py
            -> 006_audit_log: add_audit_log_entries_table.py
              -> 007_flow_analytics: add_flow_analytics_tables.py
                -> 008_quiz_constraints_v1: add_quiz_constraints.py
                  -> 009_quiz_constraints_v2: 003_add_quiz_constraints.py
                    -> 010_user_role_enum: 004_fix_user_role_enum.py
                      -> 011_other_text: 005_add_other_text_to_quiz_responses.py
                        -> 012_ai_audit_logs: 006_add_ai_audit_logs_table.py
                          -> 013_fix_quiz_response_type_constraint: 013_fix_quiz_response_type_constraint.py
                            -> 014_add_cpf_migrate_metadata: 014_add_cpf_column_migrate_metadata.py
                              -> add_dedicated_patient_columns: add_dedicated_patient_columns.py
                                -> 54ab19a5b23f: 54ab19a5b23f_merge_multiple_heads.py [MERGE]
                                  -> 3e0261295d8a: 3e0261295d8a_add_missing_user_roles.py
                                    -> 018_message_status_events: 018_create_message_status_events.py
                                      -> 019_webhook_events: 019_create_webhook_events.py
                                        -> 020_message_status_indexes: 020_add_message_status_events_indexes.py
                                          -> 021_webhook_events_indexes: 021_add_webhook_events_indexes.py
                                            -> 022_ab_experiments: 022_create_ab_experiments.py
                                              -> 023_ab_variant_assignments: 023_create_ab_variant_assignments.py
                                                -> 024_ab_experiment_metrics: 024_create_ab_experiment_metrics.py
                                                  -> 025_ab_experiment_results: 025_create_ab_experiment_results.py
                                                    -> 026_ab_experiment_audit: 026_create_ab_experiment_audit.py
                                                      -> 027_ab_experiment_monitoring: 027_create_ab_experiment_monitoring.py
                                                        -> 028_ab_testing_indexes: 028_add_ab_testing_indexes.py
                                                          -> 029_quiz_questions: 029_create_quiz_questions.py
                                                            -> 030_fix_audit_naming: 030_fix_audit_table_naming.py
                                                              -> 031_users_email_active_idx: 031_add_users_email_active_index.py
                                                                -> 032_messages_whatsapp_idx: 032_add_messages_whatsapp_id_index.py
                                                                  -> 033_audit_user_timestamp_idx: 033_add_audit_user_timestamp_index.py
                                                                    -> 034_flow_states_active_idx: 034_add_patient_flow_states_active_index.py
                                                                      -> 035_composite_indexes: 035_add_composite_performance_indexes.py
                                                                        -> 036_foreign_keys: 036_add_foreign_key_constraints.py
                                                                          -> 037_triggers: 037_add_automated_triggers.py
                                                                            -> 038_jsonb_indexes: 038_add_jsonb_gin_indexes.py
                                                                              -> 039_fulltext_search: 039_add_fulltext_search_indexes.py
                                                                                -> 3d3c49dd21c2: 3d3c49dd21c2_merge_multiple_heads.py [MERGE]
                                                                                  -> 5479068ccdaa: 5479068ccdaa_rename_audit_log_metadata_to_event_.py
                              -> add_performance_indexes: add_performance_indexes.py
                                -> 015_add_template_versioning_tables: 015_add_template_versioning_tables.py
                                  -> 016_backfill_template_versioning_data: 016_backfill_template_versioning_data.py
                                    -> 017_remove_legacy_templates: 017_remove_legacy_templates.py
                                      -> 54ab19a5b23f: 54ab19a5b23f_merge_multiple_heads.py [MERGE]
                                -> 20250929_200001: 20250929_200001_add_users_email_active_index.py
                                  -> 20250929_200002: 20250929_200002_add_messages_whatsapp_id_index.py
                                    -> 20250929_200003: 20250929_200003_add_audit_logs_user_timestamp_index.py
                                      -> 20250929_200004: 20250929_200004_add_patient_flow_states_active_index.py
                                        -> 20250929_200005: 20250929_200005_add_message_status_events_indexes.py
                                          -> 20250929_200006: 20250929_200006_add_webhook_events_indexes.py
                                            -> 20250929_200007: 20250929_200007_add_patients_doctor_id_index.py
                                              -> 20250929_200008: 20250929_200008_add_messages_patient_status_index.py
                                                -> 20250929_200009: 20250929_200009_add_flow_states_updated_index.py
                                                  -> 20250929_200010: 20250929_200010_add_quiz_responses_patient_index.py
                                                    -> 20250930_011500: 20250930_011500_add_critical_performance_indexes.py
                                                      -> add_firebase_fields: 20250930_add_firebase_fields.py
                                                        -> 20251006_add_user_sync_log_updated_at: 20251006_add_user_sync_log_updated_at.py
                                                          -> 20251006_add_risk_assessment_indexes: 20251006_add_risk_assessment_indexes.py
                                                            -> 20251007_add_sending_status: 20251007_add_message_sending_status.py
                                                              -> 3d3c49dd21c2: 3d3c49dd21c2_merge_multiple_heads.py [MERGE]
                                -> 20251009_210800: 20251009_210800_add_gin_indexes_for_search.py
                                  -> 20251009_225600: 20251009_225600_add_quiz_session_to_alerts.py
                                -> create_audit_retention: create_audit_retention_functions.py
                                  -> 3d3c49dd21c2: 3d3c49dd21c2_merge_multiple_heads.py [MERGE]
                      -> 011_remove_nurse_role: 011_remove_nurse_role.py
                        -> 54ab19a5b23f: 54ab19a5b23f_merge_multiple_heads.py [MERGE]

Chain starting from: UNKNOWN (20251009_230000_add_whatsapp_delivery_failures.py)

Chain starting from: UNKNOWN (20251009_235500_add_webhook_idempotency.py)

====================================================================================================
POTENTIAL DUPLICATE MIGRATIONS
====================================================================================================

WARNING: 'add_quiz_constraints' - 2 migrations:
     003_add_quiz_constraints.py                                            -> 009_quiz_constraints_v2
     add_quiz_constraints.py                                                -> 008_quiz_constraints_v1

WARNING: 'merge_multiple_heads' - 2 migrations:
     3d3c49dd21c2_merge_multiple_heads.py                                   -> 3d3c49dd21c2
     54ab19a5b23f_merge_multiple_heads.py                                   -> 54ab19a5b23f

====================================================================================================
RECOMMENDATIONS
====================================================================================================

1. OLD NUMBERED MIGRATIONS (001_-039_):
   Found 37 migrations with old numbering scheme
   These appear to be the original migration sequence.
   Status: WARNING - Consider consolidating into a single 'initial' migration if database can be reset

2. DATE-BASED MIGRATIONS (20251006_-20251010_):
   Found 22 recent migrations
   Status: OK - These are current and should be kept

3. DESCRIPTIVE MIGRATIONS (add_*, create_*):
   Found 6 migrations without date prefixes
   Status: WARNING - These should be reviewed - some may be test/debug migrations
      add_audit_log_entries_table.py
      add_dedicated_patient_columns.py
      add_flow_analytics_tables.py
      add_performance_indexes.py
      add_quiz_constraints.py
      create_audit_retention_functions.py

4. DUPLICATE INDEX MIGRATIONS:
   Found 24 migrations related to indexes
   Check for redundant index creation:

5. MIGRATION CHAIN HEALTH:
   WARNING - Multiple root migrations (3) - may indicate broken chain
   Consider using merge migrations or consolidating roots

6. RECOMMENDED ACTIONS:
   a. Keep all date-based migrations (202xxxxx_*)
   b. Review merge migrations to ensure they're properly connecting chains
   c. Consider consolidating old numbered migrations (001_-039_) if possible
   d. Remove any test/debug migrations from production
   e. Document the current migration chain in README

