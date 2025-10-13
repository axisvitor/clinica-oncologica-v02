-- Índice otimizado para performance do monthly quiz
-- Execute com CONCURRENTLY em produção para evitar locks

-- Quiz sessions por paciente e data (para get_patient_latest_status)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quiz_sessions_patient_started_desc
ON quiz_sessions(patient_id, started_at DESC)
WHERE session_metadata IS NOT NULL;

-- Analyze table após criação do índice
ANALYZE quiz_sessions;