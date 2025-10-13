-- 🚀 ÍNDICES CRÍTICOS DE PERFORMANCE
-- Aplicar estes índices para resolver problemas de lentidão

-- 1. MESSAGES: Índices para queries por direction e patient_id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_direction_created_at 
ON messages (direction, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_patient_id_created_at 
ON messages (patient_id, created_at DESC);

-- 2. ALERTS: Índice para queries por status
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_status_created_at 
ON alerts (status, created_at DESC);

-- 3. PATIENTS: Índice para verificação rápida de existência
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_patients_id_active 
ON patients (id) WHERE is_active = true;

-- 4. USERS: Índice para Firebase UID lookup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_firebase_uid 
ON users (firebase_uid) WHERE is_active = true;

-- 5. SESSIONS: Índice para session lookup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_session_id 
ON sessions (session_id) WHERE expires_at > NOW();

-- 6. QUIZ RESPONSES: Índice para monthly quiz stats
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quiz_responses_patient_created 
ON quiz_responses (patient_id, created_at DESC);

-- 7. REPORTS: Índice para paginação
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reports_created_at 
ON reports (created_at DESC);

-- Verificar se os índices foram criados
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE indexname LIKE 'idx_%'
ORDER BY tablename, indexname;