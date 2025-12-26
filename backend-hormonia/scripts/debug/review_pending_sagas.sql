-- ============================================================================
-- REVIEW PENDING SAGAS - Debug Script
-- Sistema Hormonia - Clinica Oncologica
-- ============================================================================

-- 1. Overview: Count sagas by status
SELECT
    status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM patient_onboarding_saga
GROUP BY status
ORDER BY count DESC;

-- 2. Failed sagas with details (last 7 days)
SELECT
    id,
    patient_id,
    status,
    current_step,
    retry_count,
    max_retries,
    error_type,
    LEFT(error_message, 100) as error_preview,
    started_at,
    failed_at,
    EXTRACT(EPOCH FROM (COALESCE(failed_at, NOW()) - started_at)) as duration_seconds
FROM patient_onboarding_saga
WHERE status IN ('FAILED', 'COMPENSATING', 'RETRY_SCHEDULED')
  AND started_at > NOW() - INTERVAL '7 days'
ORDER BY started_at DESC
LIMIT 50;

-- 3. Sagas stuck in progress (older than 1 hour)
-- NOTE: Database enum values (no IN_PROGRESS or COMPLETED_WITH_WARNINGS)
SELECT
    id,
    patient_id,
    status,
    current_step,
    error_message,
    started_at,
    EXTRACT(EPOCH FROM (NOW() - started_at))/3600 as hours_stuck
FROM patient_onboarding_saga
WHERE status IN ('STARTED', 'STEP_1_PATIENT_CREATED',
                 'STEP_3_FLOW_INITIALIZED', 'STEP_4_MESSAGE_SENT')
  AND started_at < NOW() - INTERVAL '1 hour'
ORDER BY started_at ASC;

-- 4. Error distribution analysis
SELECT
    error_type,
    COUNT(*) as occurrences,
    MAX(started_at) as last_occurrence,
    AVG(retry_count) as avg_retries
FROM patient_onboarding_saga
WHERE error_type IS NOT NULL
  AND started_at > NOW() - INTERVAL '30 days'
GROUP BY error_type
ORDER BY occurrences DESC;

-- 5. Sagas by step with failure rates
SELECT
    current_step,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
    COUNT(*) FILTER (WHERE status = 'COMPLETED') as completed,
    ROUND(COUNT(*) FILTER (WHERE status = 'FAILED') * 100.0 / NULLIF(COUNT(*), 0), 2) as failure_rate
FROM patient_onboarding_saga
WHERE started_at > NOW() - INTERVAL '30 days'
GROUP BY current_step
ORDER BY current_step;

-- 6. Retry scheduled sagas needing attention
SELECT
    id,
    patient_id,
    status,
    retry_count,
    next_retry_at,
    last_retry_at,
    error_message
FROM patient_onboarding_saga
WHERE status = 'RETRY_SCHEDULED'
  AND next_retry_at < NOW()
ORDER BY next_retry_at ASC;

-- 7. Daily saga completion rates (last 14 days)
SELECT
    DATE(started_at) as date,
    COUNT(*) as total_started,
    COUNT(*) FILTER (WHERE status = 'COMPLETED') as completed,
    COUNT(*) FILTER (WHERE status = 'COMPLETED_WITH_WARNINGS') as with_warnings,
    COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
    ROUND(COUNT(*) FILTER (WHERE status IN ('COMPLETED', 'COMPLETED_WITH_WARNINGS')) * 100.0 / NULLIF(COUNT(*), 0), 2) as success_rate
FROM patient_onboarding_saga
WHERE started_at > NOW() - INTERVAL '14 days'
GROUP BY DATE(started_at)
ORDER BY date DESC;

-- 8. Execution log analysis for failed sagas
SELECT
    id,
    patient_id,
    status,
    current_step,
    jsonb_array_length(COALESCE(execution_log, '[]'::jsonb)) as log_entries,
    execution_log->-1->>'action' as last_action,
    execution_log->-1->>'status' as last_action_status,
    execution_log->-1->>'message' as last_action_message
FROM patient_onboarding_saga
WHERE status = 'FAILED'
  AND started_at > NOW() - INTERVAL '7 days'
ORDER BY started_at DESC
LIMIT 20;

-- 9. Patients with multiple saga attempts
SELECT
    patient_id,
    COUNT(*) as saga_attempts,
    COUNT(*) FILTER (WHERE status = 'COMPLETED') as successful,
    COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
    MAX(started_at) as last_attempt
FROM patient_onboarding_saga
WHERE patient_id IS NOT NULL
GROUP BY patient_id
HAVING COUNT(*) > 1
ORDER BY saga_attempts DESC
LIMIT 20;

-- 10. Full details for specific saga (replace UUID)
-- SELECT * FROM patient_onboarding_saga WHERE id = 'YOUR-SAGA-UUID-HERE';
